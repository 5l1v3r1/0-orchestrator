#!/usr/bin/python3
import argparse
import subprocess
import sys
import time
import yaml
from zeroos.orchestrator.sal.Node import Node

class OrchestratorInstaller:
    def __init__(self):
        self.node = None
        self.flist = "https://hub.gig.tech/maxux/0-orchestrator-full-autosetup.flist"
        self.ctname = None

    """
    remote: remote address of the node
    auth: password (jwt token usualy) nfor client
    """
    def connector(self, remote, auth):
        print("[+] contacting zero-os server: %s" % remote)
        while True:
            try:
                node = Node(remote, password=auth)
                node.client.timeout = 180
                break

            except RuntimeError as e:
                print("[-] cannot connect server (make sure the server is reachable), retrying")
                time.sleep(1)
                pass

        self.node = node

        return node

    """
    node: connected node object
    ctname: container name
    ztnetwork: zerotier network the container should join
    """
    def prepare(self, ctname, ztnetwork):
        self.ctname = ctname

        print("[+] open http and https ports")
        opened = self.node.client.nft.list()
        if 'tcp dport 80 accept' not in opened:
            self.node.client.nft.open_port(80)

        if 'tcp dport 443 accept' not in opened:
            self.node.client.nft.open_port(443)

        print("[+] starting orchestrator container")
        network = [
            {'type': 'default'},
            {'type': 'zerotier', 'id': ztnetwork}
        ]

        """
        export PATH="/opt/jumpscale9/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        export PYTHONPATH="/opt/jumpscale9/lib/:/opt/code/github/jumpscale/core9/:/opt/code/github/jumpscale/prefab9/:/opt/code/github/jumpscale/ays9:/opt/code/github/jumpscale/lib9:/opt/code/github/jumpscale/portal9"
        export HOME="/root"
        export LC_ALL="C.UTF-8"
        export LC_LANG="UTF-8"
        """

        env = {
            "PATH": "/opt/jumpscale9/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH": "/opt/jumpscale9/lib/:/opt/code/github/jumpscale/core9/:/opt/code/github/jumpscale/prefab9/:/opt/code/github/jumpscale/ays9:/opt/code/github/jumpscale/lib9:/opt/code/github/jumpscale/portal9",
            "HOME": "/root",
            "LC_ALL": "C.UTF-8",
            "LC_LANG": "UTF-8"
        }

        if not self.node.client.filesystem.exists('/var/cache/containers/orchestrator'):
            self.node.client.filesystem.mkdir('/var/cache/containers/orchestrator')

        cn = self.node.containers.create(
            name=ctname,
            flist=self.flist,
            hostname='bootstrap',
            nics=network,ports={80:80, 443:443},
            mounts={'/var/cache/containers/orchestrator': '/optvar'},
            env=env
        )

        print("[+] setting up and starting ssh server")
        cn.client.bash('dpkg-reconfigure openssh-server').get()
        cn.client.bash('/etc/init.d/ssh start').get()

        print("[+] allowing local ssh key")
        keys = subprocess.run(["ssh-add", "-L"], stdout=subprocess.PIPE)
        strkeys = keys.stdout.decode('utf-8')

        fd = cn.client.filesystem.open("/root/.ssh/authorized_keys", "w")
        cn.client.filesystem.write(fd, strkeys.encode('utf-8'))
        cn.client.filesystem.close(fd)

        # make sure the enviroment is also set in bashrc for when ssh is used
        print("[+] setting environment variables")
        fd = cn.client.filesystem.open("/root/.bashrc", "a")
        for k, v in env.items():
            export = "export %s=%s\n" % (k, v)
            cn.client.filesystem.write(fd, export.encode('utf-8'))
        cn.client.filesystem.close(fd)

        print("[+] waiting for zerotier")
        containeraddr = self.containerZt(cn)

        print("[+] generating ssh keys")
        cn.client.bash("ssh-keygen -f /root/.ssh/id_rsa -t rsa -N ''").get()
        publickey = cn.client.bash("cat /root/.ssh/id_rsa.pub").get()

        return {'address': containeraddr, 'publickey': publickey.stdout}

    """
    upstream: git upstream address of orchestrator repository
    email: email address used for git and caddy certificates
    organization: organization name ays should join
    """
    def configure(self, upstream, email, organization=None):
        print("[+] configuring services")
        cn = self.node.containers.get(self.ctname)

        if organization:
            print("[+] setting organization")

            config = "\n\n[ays]\n"
            config += "production = true\n"
            config += "\n"
            config += "[ays.oauth]\n"
            config += "jwt_key = \"MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAES5X8XrfKdx9gYayFITc89wad4usrk0n27MjiGYvqalizeSWTHEpnd7oea9IQ8T5oJjMVH5cc0H5tFSKilFFeh//wngxIyny66+Vq5t5B0V0Ehy01+2ceEon2Y0XDkIKv\"\n"
            config += "organization = \"%s\"\n" % organization

            if not cn.client.filesystem.exists("/optvar/cfg"):
                cn.client.filesystem.mkdir("/optvar/cfg")

            fd = cn.client.filesystem.open("/optvar/cfg/jumpscale9.toml", "a")
            cn.client.filesystem.write(fd, config.encode('utf-8'))
            cn.client.filesystem.close(fd)

        print("[+] configuring git client")
        cn.client.bash("git config --global user.name 'AYS System'").get()
        cn.client.bash("git config --global user.email '%s'" % email).get()

        print("[+] configuring upstream repository")
        cn.client.filesystem.mkdir("/optvar/cockpit_repos")
        cn.client.bash("git clone %s /tmp/upstream" % upstream).get()
        resp = cn.client.bash("cd /tmp/upstream && git rev-parse HEAD").get()

        # upstream is empty, let create a new repository
        if resp.code != 0:
            cn.client.filesystem.mkdir("/tmp/upstream/services")
            cn.client.filesystem.mkdir("/tmp/upstream/actorTemplates")
            cn.client.filesystem.mkdir("/tmp/upstream/actors")
            cn.client.filesystem.mkdir("/tmp/upstream/blueprints")

            cn.client.bash("touch /tmp/upstream/.ays").get()
            cn.client.bash("cd /tmp/upstream/ && git init").get()
            cn.client.bash("cd /tmp/upstream/ && git remote add origin %s" % upstream).get()
            cn.client.bash("cd /tmp/upstream/ && git add .").get()
            cn.client.bash("cd /tmp/upstream/ && git commit -m 'Initial commit'").get()
            # cn.client.bash("cd /tmp/upstream/ && git push origin master").get()

            # this may need ssh agent.
            cn.client.bash("cd /tmp/upstream/ && git push origin master").get()

        # moving upstream to target cockpit repository
        cn.client.bash("mv /tmp/upstream /optvar/cockpit_repos/orchestrator-server").get()

        return True

    def blueprint(self):
        print("[+] building blueprint")
        cn = self.node.containers.get(self.ctname)

        orchestratorhome = "/opt/code/github/zero-os/0-orchestrator"

        print("[+] building configuration blueprint")
        configfile = cn.client.bash("cat %s/autosetup/config-template.yaml" % orchestratorhome).get()
        print(configfile.stdout)
        config = yaml.load(configfile.stdout)

        print(config)
        # edit config

        blueprint = "/optvar/cockpit_repos/orchestrator-server/blueprints/configuration.bp"
        fd = cn.client.filesystem.open(blueprint, "w")
        cn.client.filesystem.write(fd, yaml.dumps(config))
        cn.client.filesystem.close(fd)

        # this need to be done after ays starts
        # print("[+] executing blueprint")

    def containerZt(self, cn):
        while True:
            ztinfo = cn.client.zerotier.list()
            ztdata = ztinfo[0]

            if len(ztdata['assignedAddresses']) == 0:
                print("[+] please authorize the zerotier member with the mac address %s" % ztdata['mac'])
                time.sleep(1)
                continue

            return ztdata['assignedAddresses'][0].split('/')[0]



    def starter(self, email, domain=None, organization=None):
        jobs = {}
        cn = self.node.containers.get(self.ctname)

        running = self.running_processes(cn)
        if len(running) == 3:
            print("[+] all processes already running")
            return

        if 'ays' not in running:
            print("[+] starting ays")
            jobs['ays'] = cn.client.system('python3 main.py --host 127.0.0.1 --port 5000 --log info', dir='/opt/code/github/jumpscale/ays9')

        if 'orchestrator' not in running:
            print("[+] starting 0-orchestrator")
            if organization:
                jobs['orchestrator'] = cn.client.system('/usr/local/bin/orchestratorapiserver --bind localhost:8080 --ays-url http://127.0.0.1:5000 --ays-repo orchestrator-server --org "%s"' % organization)

            else:
                jobs['orchestrator'] = cn.client.system('/usr/local/bin/orchestratorapiserver --bind localhost:8080 --ays-url http://127.0.0.1:5000 --ays-repo orchestrator-server')

        if 'caddy' not in running:
            if domain:
                caddyfile = """
                %s {
                    proxy / localhost:8080
                }
                """ % domain
            else:
                caddyfile = """
                :443 {
                    proxy / localhost:8080
                    tls self_signed
                }
                :80 {
                    proxy / localhost:8080
                }
                """

            print("[+] starting caddy")
            cn.client.filesystem.mkdir('/etc/caddy')

            fd = cn.client.filesystem.open("/etc/caddy/Caddyfile", "w")
            cn.client.filesystem.write(fd, caddyfile.encode('utf-8'))
            cn.client.filesystem.close(fd)

            jobs['caddy'] = cn.client.system('/usr/local/bin/caddy -agree -email %s -conf /etc/caddy/Caddyfile -quic' % email)

        print("[+] all processes started")

    """
    def stop(ip):
        node = Node(ip)
        cn = self.node.containers.get('tftprod')

        def kill(pid):
            cn.client.process.kill(pid)

        for ps in cn.client.process.list():
            if ps['cmdline'].find("caddy") != -1:
                print('[+] kill caddy')
                kill(ps['pid'])
            if ps['cmdline'].find("orchestratorapiserver") != -1:
                print('[+] kill orchestrator')
                kill(ps['pid'])
            if ps['cmdline'].find("/opt/jumpscale9/bin/python3 main.py") != -1:
                print('[+] kill ays')
                kill(ps['pid'])
    """

    def running_processes(self, cn):
        running = set()

        for ps in cn.client.process.list():
            if ps['cmdline'].find("caddy") != -1:
                running.add('caddy')

            if ps['cmdline'].find("orchestratorapiserver") != -1:
                running.add('orchestrator')

            if ps['cmdline'].find("/opt/jumpscale9/bin/python3 main.py") != -1:
                running.add('ays')

        return running

    """
    You can just extends this class to implements theses hooks
    This will allows you to customize the setup
    """
    def pre_prepare(self):
        pass

    def post_prepare(self):
        pass

    def pre_configure(self):
        pass

    def post_configure(self):
        pass

    def pre_starter(self):
        pass

    def post_starter(self):
        pass


if __name__ == "__main__":
    print("[+] initializing orchestrator bootstrapper")

    email = "info@gig.tech"

    parser = argparse.ArgumentParser(description='Manage Threefold Orchestrator')
    parser.add_argument('--server', type=str, help='zero-os remote server to connect', required=True)
    parser.add_argument('--password', type=str, help='password (jwt) used to connect the host')
    parser.add_argument('--container', type=str, help='container deployment name', required=True)
    parser.add_argument('--domain', type=str, help='domain on which caddy should be listening, if not specified caddy will listen on port 80 and 443, but with self-signed certificate')
    parser.add_argument('--ztnet', type=str, help='zerotier network id of the container', required=True)
    parser.add_argument('--upstream', type=str, help='remote upstream git address', required=True)
    parser.add_argument('--email', type=str, help='email used by caddy for certificates')
    parser.add_argument('--organization', type=str, help='itsyou.online organization of ays')
    # parser.add_argument('--volume', type=str, help='extra volume to mount')
    args = parser.parse_args()

    if args.email != None:
        email = args.email

    print("[+] ---------------------------------------------")
    print("[+] remote server: %s" % args.server)
    print("[+] zerotier network: %s" % args.ztnet)
    print("[+] domain name: %s" % args.domain)
    print("[+] upstream git: %s" % args.upstream)
    print("[+] certificates email: %s" % email)
    print("[+] ays organization: %s" % args.organization)
    print("[+] ---------------------------------------------")

    installer = OrchestratorInstaller()

    print("[+] initializing connection")
    node = installer.connector(args.server, args.password)

    print("[+] hook: pre-prepare")
    installer.pre_prepare()

    print("[+] hook: prepare")
    prepared = installer.prepare(args.container, args.ztnet)
    print(prepared)

    print("[+] hook: post-prepare")
    installer.post_prepare()

    print("[+] hook: pre-configure")
    installer.pre_configure()

    print("[+] hook: configure")
    installer.configure(args.upstream, email, args.organization)
    installer.blueprint()

    print("[+] hook: post-configure")
    installer.post_configure()

    print("[+] hook: pre-starter")
    installer.pre_starter()

    print("[+] hook: starter")
    installer.starter(email, args.domain, args.organization)

    print("[+] hook: post-starter")
    installer.post_starter()
