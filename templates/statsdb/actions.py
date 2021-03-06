from js9 import j


def input(job):
    ays_repo = job.service.aysrepo
    services = ays_repo.servicesFind(actor=job.service.model.dbobj.actorName)

    if services and job.service.name != services[0].name:
        raise j.exceptions.RuntimeError('Repo can\'t contain multiple statsdb services')


def init(job):
    from zeroos.orchestrator.configuration import get_jwt_token
    from zeroos.orchestrator.sal.templates import render
    from zeroos.orchestrator.sal.StorageCluster import BlockCluster, ObjectCluster
    service = job.service

    influxdb_actor = service.aysrepo.actorGet('influxdb')

    args = {
        'node': service.model.data.node,
        'port': service.model.data.port,
        'databases': ['statistics']
    }
    influxdb_service = influxdb_actor.serviceCreate(instance='statsdb', args=args)
    service.consume(influxdb_service)

    grafana_actor = service.aysrepo.actorGet('grafana')

    args = {
        'node': service.model.data.node,
        'influxdb': ['statsdb']
    }
    grafana_service = grafana_actor.serviceCreate(instance='statsdb', args=args)
    service.consume(grafana_service)

    dashboard_actor = service.aysrepo.actorGet('dashboard')

    args = {
        'grafana': 'statsdb',
        'dashboard': render('dashboards/overview.json')
    }
    dashboard_actor.serviceCreate(instance='overview', args=args)

    # Install stats_collector on all nodes
    stats_collector_actor = job.service.aysrepo.actorGet('stats_collector')
    node_services = job.service.aysrepo.servicesFind(actor='node.zero-os')
    for node_service in node_services:
        stats_collector_service = get_stats_collector_from_node(node_service)
        if not stats_collector_service:
            args = {
                'node': node_service.name,
                'port': job.service.model.data.port,
                'ip': job.service.parent.model.data.redisAddr,

            }
            stats_collector_service = stats_collector_actor.serviceCreate(instance=node_service.name, args=args)
            stats_collector_service.consume(node_service)

    # Create storage cluster dashboards
    blockcluster_services = job.service.aysrepo.servicesFind(actor='storagecluster.block')
    objectcluster_services = job.service.aysrepo.servicesFind(actor='storagecluster.object')

    job.context['token'] = get_jwt_token(job.service.aysrepo)
    for clusterservice in blockcluster_services:
        cluster = BlockCluster.from_ays(clusterservice, job.context['token'])
        board = cluster.dashboard

        args = {
            'grafana': 'statsdb',
            'dashboard': board
        }
        dashboard_actor.serviceCreate(instance=cluster.name, args=args)
        stats_collector_service.consume(clusterservice)

    for clusterservice in objectcluster_services:
        cluster = ObjectCluster.from_ays(clusterservice, job.context['token'])
        board = cluster.dashboard

        args = {
            'grafana': 'statsdb',
            'dashboard': board
        }
        dashboard_actor.serviceCreate(instance=cluster.name, args=args)
        stats_collector_service.consume(clusterservice)


def get_influxdb(service, force=True):
    influxdbs = service.producers.get('influxdb')
    if not influxdbs:
        if force:
            raise RuntimeError('Service didn\'t consume any influxdbs')
        else:
            return
    return influxdbs[0]


def get_grafana(service, force=True):
    grafanas = service.producers.get('grafana')
    if not grafanas:
        if force:
            raise RuntimeError('Service didn\'t consume any grafana')
        else:
            return
    return grafanas[0]


def get_stats_collector_from_node(service):
    stats_collectors_services = service.consumers.get('stats_collector')
    if stats_collectors_services:
        return stats_collectors_services[0]


def install(job):
    start(job)


def start(job):
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)
    job.service.model.data.status = 'running'
    job.service.saveAll()
    influxdb = get_influxdb(job.service)
    grafana = get_grafana(job.service)
    influxdb.executeAction('install', context=job.context)
    grafana.executeAction('install', context=job.context)

    # Start stats_collector on all nodes
    node_services = job.service.aysrepo.servicesFind(actor='node.zero-os')
    for node_service in node_services:
        stats_collector_service = get_stats_collector_from_node(node_service)

        if stats_collector_service:
            if stats_collector_service.model.data.status == 'running':
                stats_collector_service.executeAction('stop', context=job.context)
            stats_collector_service.executeAction('start', context=job.context)


def stop(job):
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)
    job.service.model.data.status = 'halted'
    job.service.saveAll()

    influxdb = get_influxdb(job.service)
    grafana = get_grafana(job.service)
    influxdb.executeAction('stop', context=job.context)
    grafana.executeAction('stop', context=job.context)

    job.service.model.data.status = 'halted'
    job.service.saveAll()

    node_services = job.service.aysrepo.servicesFind(actor='node.zero-os')
    for node_service in node_services:
        stats_collector_service = get_stats_collector_from_node(node_service)
        if stats_collector_service and stats_collector_service.model.data.status == 'running':
            stats_collector_service.executeAction('stop', context=job.context)


def uninstall(job):
    from zeroos.orchestrator.configuration import get_jwt_token

    job.context['token'] = get_jwt_token(job.service.aysrepo)

    influxdb = get_influxdb(job.service, False)
    grafana = get_grafana(job.service, False)

    if grafana:
        grafana.executeAction('uninstall', context=job.context)
    if influxdb:
        influxdb.executeAction('uninstall', context=job.context)

    node_services = job.service.aysrepo.servicesFind(actor='node.zero-os')
    for node_service in node_services:
        stats_collector_service = get_stats_collector_from_node(node_service)
        if stats_collector_service:
            stats_collector_service.executeAction('uninstall', context=job.context)
    job.service.delete()


def processChange(job):
    from zeroos.orchestrator.configuration import get_jwt_token_from_job
    service = job.service
    args = job.model.args
    if args.get('changeCategory') != 'dataschema' or service.model.actionsState['install'] in ['new', 'scheduled']:
        return

    if 'port' in args:
        service.model.data.port = args['port']
        service.saveAll()
        influxdb = get_influxdb(job.service)
        job.context['token'] = get_jwt_token_from_job(job)
        influxdb.executeAction('processChange', context=job.context, args={'port': args['port']})

def monitor(job):
    from zeroos.orchestrator.configuration import get_jwt_token

    if job.service.model.data.status != 'running':
        return

    job.context['token'] = get_jwt_token(job.service.aysrepo)
    start(job)


def init_actions_(service, args):
    return {
        'init': [],
        'install': ['init'],
        'monitor': ['start'],
        'delete': ['uninstall'],
        'uninstall': [],
    }
