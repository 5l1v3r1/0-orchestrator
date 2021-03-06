from js9 import j


def input(job):
    # make sure we always consume all the filesystems used in the mounts property
    args = job.model.args
    mounts = args.get('mounts', [])
    if 'filesystems' in args:
        raise j.exceptions.InputError("Filesystem should not be passed from the blueprint")
    args['filesystems'] = []
    filesystems = args['filesystems']
    for mount in mounts:
        if mount['filesystem'] not in filesystems:
            args['filesystems'].append(mount['filesystem'])

    args['bridges'] = []
    for nic in args.get('nics', []):
        if nic['type'] == 'bridge':
            args['bridges'].append(nic['id'])

    return args


def init(job):
    from zeroos.orchestrator.sal.Node import Node
    from zeroos.orchestrator.configuration import get_jwt_token
    import re

    service = job.service
    job.context['token'] = get_jwt_token(service.aysrepo)
    for nic in service.model.data.nics:
        if nic.hwaddr:
            pattern = re.compile(r'^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')
            if not pattern.match(nic.hwaddr):
                raise j.exceptions.Input('Hwaddr: string is not a valid mac address.')
        if nic.type == 'vlan':
            break
    else:
        return

    node = Node.from_ays(service.parent, job.context['token'])
    ovs_container = node.client.container.find('ovs')
    if not ovs_container:
        raise j.exceptions.Input('OVS container needed to run this blueprint')


def install(job):
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)

    job.service.model.data.status = "halted"

    job.service.executeAction('start', context=job.context)


def get_member(zerotier, zerotiernodeid, nicid):
    import time
    start = time.time()
    while start + 60 > time.time():
        resp = zerotier.network.getMember(zerotiernodeid, nicid)
        if resp.content:
            return resp.json()
        time.sleep(0.5)
    raise j.exceptions.RuntimeError('Could not find member on zerotier network')


def wait_for_interface(container):
    import time
    start = time.time()
    while start + 60 > time.time():
        for link in container.client.ip.link.list():
            if link['type'] == 'tun':
                return
        time.sleep(0.5)
    raise j.exceptions.RuntimeError("Could not find zerotier network interface")


def zerotier_nic_config(service, logger, container, nic):
    from zerotier import client
    wait_for_interface(container)
    service.model.data.zerotiernodeid = container.client.zerotier.info()['address']
    if nic.token:
        zerotier = client.Client()
        zerotier.set_auth_header('bearer {}'.format(nic.token))
        member = get_member(zerotier, service.model.data.zerotiernodeid, nic.id)
        if not member['config']['authorized']:
            # authorized new member
            logger.info("authorize new member {} to network {}".format(member['nodeId'], nic.id))
            member['config']['authorized'] = True
            zerotier.network.updateMember(member, member['nodeId'], nic.id)


def start(job):
    from zeroos.orchestrator.sal.Container import Container
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)

    service = job.service
    container = Container.from_ays(service, job.context['token'], logger=service.logger)
    container.start()

    if container.is_running():
        service.model.data.status = "running"
    else:
        raise j.exceptions.RuntimeError("container didn't start")

    has_zt_nic = False
    for nic in service.model.data.nics:
        if nic.type == 'zerotier':
            has_zt_nic = True
            zerotier_nic_config(service, job.logger, container, nic)

    if has_zt_nic and not service.model.data.identity:
        service.model.data.identity = container.client.zerotier.info()['secretIdentity']

    service.saveAll()


def stop(job):
    from zeroos.orchestrator.sal.Container import Container
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)

    container = Container.from_ays(job.service, job.context['token'], logger=job.service.logger)
    container.stop()

    if not container.is_running():
        job.service.model.data.status = "halted"
    else:
        raise j.exceptions.RuntimeError("container didn't stop")


def processChange(job):
    service = job.service
    args = job.model.args

    containerdata = service.model.data.to_dict()
    nicchanges = 'nics' in args and containerdata.get('nics') != args['nics']

    if nicchanges:
        update(job, args['nics'])


def update(job, updated_nics):
    from zeroos.orchestrator.sal.Container import Container
    from zeroos.orchestrator.utils import write_status_code_error
    from zeroos.core0.client.client import ResultError
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)

    service = job.service
    token = job.context['token']
    logger = job.logger
    container = Container.from_ays(service, token, logger=service.logger)
    cl = container.node.client.container

    current_nics = service.model.data.to_dict()['nics']

    def get_nic_id(nic):
        # use combination of type and id as identifier, cannot use name as it is optional and not unique while id is.
        if not nic.get('id') and nic['type'] == 'default':
            nic['id'] = 'default'
        return "{}:{}".format(nic['type'], nic['id'])

    # find the index of the nic in the list returned by client.container.list()
    def get_nic_index(nic):
        all_nics = cl.list()[str(container.id)]['container']['arguments']['nics']
        nic_id = get_nic_id(nic)
        for i in range(len(all_nics)):
            if all_nics[i]['state'] == 'configured' and nic_id == get_nic_id(all_nics[i]):
                logger.info("nic with id {} found on index {}".format(nic_id, i))
                return i
        raise j.exceptions.RuntimeError("Nic with id {} not found".format(nic_id))

    ids_current_nics = [get_nic_id(n) for n in current_nics]
    ids_updated_nics = [get_nic_id(n) for n in updated_nics]

    # check for duplicate interfaces
    if len(ids_updated_nics) != len(set(ids_updated_nics)):
        raise j.exceptions.RuntimeError("Duplicate nic detected")

    # check for nics to be removed
    for nic in current_nics:
        if get_nic_id(nic) not in ids_updated_nics:
            logger.info("Removing nic from container {}: {}".format(container.id, nic))
            cl.nic_remove(container.id, get_nic_index(nic))

    # update nics model
    old_nics = [i for i in service.model.data.nics]
    service.model.data.nics = updated_nics

    # check for nics to be added
    for nic in service.model.data.nics:
        nic_dict = nic.to_dict()
        if get_nic_id(nic_dict) not in ids_current_nics:
            nic_dict.pop('token', None)
            logger.info("Adding nic to container {}: {}".format(container.id, nic_dict))
            try:
                cl.nic_add(container.id, nic_dict)
            except ResultError as e:
                write_status_code_error(job, e)
                service.model.data.nics = old_nics
                service.saveAll()
                raise j.exceptions.Input(str(e))
            if nic.type == 'zerotier':
                # do extra zerotier configuration
                zerotier_nic_config(service, logger, container, nic)

    service.saveAll()


def monitor(job):
    from zeroos.orchestrator.configuration import get_jwt_token
    from zeroos.orchestrator.sal.Node import Node
    from zeroos.orchestrator.sal.Container import Container

    service = job.service
    if service.model.actionsState['install'] != 'ok' or service.parent.model.data.status != 'running':
        return

    token = get_jwt_token(job.service.aysrepo)
    node = Node.from_ays(service.parent, token, timeout=5)
    if not node.is_configured():
        return

    container = Container.from_ays(job.service, token, logger=service.logger)
    running = container.is_running()

    if not running and service.model.data.status == 'running' and container.node.is_configured(service.parent.name):
        ovs_name = '{}_ovs'.format(container.node.name)
        if ovs_name != service.name:
            ovs_service = service.aysrepo.serviceGet(role='container', instance=ovs_name)
            ovs_container = Container.from_ays(ovs_service, token)
            if not ovs_container.is_running():
                job.logger.warning\
                    ("Can't attempt to restart container {}, container {} is not running".format(
                        service.name, ovs_name))
        try:
            job.logger.warning("container {} not running, trying to restart".format(service.name))
            service.model.dbobj.state = 'error'
            container.start()

            if container.is_running():
                service.model.dbobj.state = 'ok'
        except:
            job.logger.error("can't restart container {} not running".format(service.name))
            service.model.dbobj.state = 'error'
    elif running and service.model.data.status == 'halted':
        try:
            job.logger.warning("container {} running, trying to stop".format(service.name))
            service.model.dbobj.state = 'error'
            container.stop()
            running, _ = container.is_running()
            if not running:
                service.model.dbobj.state = 'ok'
        except:
            job.logger.error("can't stop container {} is running".format(service.name))
            service.model.dbobj.state = 'error'


def watchdog_handler(job):
    import asyncio
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)

    service = job.service
    etcd = service.consumers.get('etcd')
    if not etcd:
        return

    etcd_cluster = etcd[0].consumers.get('etcd_cluster')
    if etcd_cluster:
        etcd_cluster[0].self_heal_action('watchdog_handler')