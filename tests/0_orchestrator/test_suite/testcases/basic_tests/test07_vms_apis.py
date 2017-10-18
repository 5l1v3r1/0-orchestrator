import random, time
from testcases.testcases_base import TestcasesBase
import unittest, time
from testcases.core0_client import Client


class TestVmsAPI(TestcasesBase):
    @classmethod
    def setUpClass(cls):
        self = cls()
        super(TestVmsAPI, self).setUp()

        TestVmsAPI.nodeid = self.nodeid
        nodes = [TestVmsAPI.nodeid]
        number_of_free_disks, disk_type = self.get_max_available_free_disks(nodes)

        storageclusters = self.storageclusters_api.get_storageclusters()
        if not storageclusters.json():

            if not number_of_free_disks :
                self.skipTest('[*] No free disks to create storage cluster')

            self.lg.info('[*] Create storagecluster')
            response, cluster = self.storageclusters_api.post_storageclusters(nodes=nodes, driveType=disk_type, servers=1)
            self.assertEqual(response.status_code, 201)
            storagecluster = cluster['label']
        
        else:
            storagecluster = storageclusters.json()[0]
  
        self.lg.info('[*] Create vdiskstorage')
        response, vdiskstorage = self.vdisks_api.post_vdiskstorage(storagecluster=storagecluster)
        self.assertEqual(response.status_code, 201)
        
        self.lg.info('[*] Import image to vdiskstorage')
        response, imagedata = self.vdisks_api.post_import_image(vdiskstorageid=vdiskstorage['id'])
        self.assertEqual(response.status_code, 201)

        TestVmsAPI.vdiskstorageid = vdiskstorage['id']
        TestVmsAPI.imageid = imagedata["imageName"]

        
        

    @classmethod
    def tearDownClass(cls):
        self = cls()
        self.lg.info('[*] Delete image')
        self.vdisks_api.delete_image(TestVmsAPI.vdiskstorageid, TestVmsAPI.imageid)

        
    def setUp(self):
        super().setUp()

        self.lg.info(' [*] Create ssh client contaienr')
        response, self.ssh_client_data = self.containers_api.post_containers(self.nodeid, hostNetworking=True)
        self.assertEqual(response.status_code, 201)
        self.ssh_client = self.core0_client.get_container_client(self.ssh_client_data['name'])

        self.lg.info('[*] Create vdisk')
        body = {"type": "boot", "blocksize": 4096, "readOnly": False, "size": 15}        
        response, self.vdisk = self.vdisks_api.post_vdisks(vdiskstorageid=TestVmsAPI.vdiskstorageid, imageid=TestVmsAPI.imageid, **body)
        self.assertEqual(response.status_code, 201)

        self.disks = [{"vdiskid": self.vdisk['id'], "maxIOps": 2000}]
        self.lg.info(' [*] Create virtual machine (VM0) on node (N0)')
        response, self.data = self.vms_api.post_nodes_vms(node_id=self.nodeid, memory=1024, cpu=1, disks=self.disks)
        self.assertEqual(response.status_code, 201)

        response = self.vms_api.get_nodes_vms_vmid(nodeid=self.nodeid, vmid=self.data['id'])
        self.assertEqual(response.status_code, 200)

        vm_vnc_port = response.json()['vnc'] - 5900
        vm_vnc_url = '{}:{}'.format(self.nodeip, vm_vnc_port)

        time.sleep(20)

        self.enable_ssh_access(vm_vnc_url)
        self.vm_ip_address = self.get_vm_default_ipaddress(self.data['id'])


    def tearDown(self):
        self.lg.info(' [*] Delete virtual machine (VM0)')
        self.vms_api.delete_nodes_vms_vmid(self.nodeid, self.data['id'])

        self.lg.info(' [*] Delete virtual disk (VD0)')
        self.vdisks_api.delete_vdisks_vdiskid(TestVmsAPI.vdiskstorageid, self.vdisk['id'])

        self.lg.info(' [*] Delete ssh client contaienr')
        self.containers_api.delete_containers_containerid(self.nodeid, self.ssh_client_data['name'])
        
        super(TestVmsAPI, self).tearDown()


    def test001_get_nodes_vms_vmid(self):
        """ GAT-067
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Get virtual machine (VM0), should succeed with 200.
        #. Get non existing virtual machine, should fail with 404.
        """
        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')

        self.lg.info(' [*] Get virtual machine (VM0), should succeed with 200')
        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
 
        for key in ['id', 'memory', 'cpu', 'disks']:
            self.assertEqual(self.data[key], response.json()[key])

        self.assertEqual(response.json()['status'], 'running')

        core0_vm_list = self.core0_client.client.kvm.list()
        self.assertIn(self.data['id'], [x['name'] for x in core0_vm_list])

        self.lg.info(' [*] Get non existing virtual machine, should fail with 404')
        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, 'fake_vm')
        self.assertEqual(response.status_code, 404)


    def test002_get_node_vms(self):
        """ GAT-068
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. List node (N0) virtual machines, virtual machine (VM0) should be listed, should succeed with 200.
        """
        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed with 200')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')

        self.lg.info('[*] List node (N0) virtual machines, (VM0) should be listed, should succeed with 200')
        response = self.vms_api.get_nodes_vms(self.nodeid)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.data['id'], [x['id'] for x in response.json()])

    def test004_put_nodes_vms_vmid(self):
        """ GAT-070
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Update virtual machine (VM1), should succeed with 204.
        #. Get virtual machine (VM1), should succeed with 200.
        #. Update virtual machine with missing parameters, should fail with 400.
        """

        body = {
            "memory": 2048,
            "cpu": 2,
            "nics": [{"type":"default"}],
            "disks": self.disks
        }

        self.lg.info(' [*] Stop virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_stop(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'halted')

        self.lg.info(' [*] Update virtual machine (VM1), should succeed with 204')
        response = self.vms_api.put_nodes_vms_vmid(self.nodeid, self.data['id'], body)
        self.assertEqual(response.status_code, 204)

        self.lg.info(' [*] Start virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_start(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'running')

        for key in ['memory', 'cpu', 'disks']:
            self.assertEqual(body[key], response.json()[key])

        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed')
        vm_ip_address = self.get_vm_default_ipaddress(self.data['id'])        
        response = self.execute_command_inside_vm(self.ssh_client, vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')

        self.lg.info(' [*] Update virtual machine with missing parameters, should fail with 400')
        body = {"id": self.random_string()}
        response = self.vms_api.put_nodes_vms_vmid(self.nodeid, self.data['id'], body)
        self.assertEqual(response.status_code, 400)

        
    def test005_get_nodes_vms_vmid_info(self):
        """ GAT-071
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Get virtual machine (VM0) info, should succeed with 200.
        #. Get non existing virtual machine info, should fail with 404.
        """
        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')

        self.lg.info(' [*] Get virtual machine (VM0) info, should succeed with 200')
        response = self.vms_api.get_nodes_vms_vmid_info(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)

        self.lg.info(' [*] Get non existing virtual machine info, should fail with 404')
        response = self.vms_api.get_nodes_vms_vmid_info(self.nodeid, self.rand_str())
        self.assertEqual(response.status_code, 404, " [*] get non existing vm returns %i" % response.status_code)

    def test006_delete_nodes_vms_vmid(self):
        """ GAT-072
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Delete virtual machine (VM0), should succeed with 204.
        #. List kvms in python client, (VM0) should be gone.
        #. Delete non existing virtual machine, should fail with 404.
        """
        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')

        self.lg.info(' [*] Delete virtual machine (VM0), should succeed with 204')
        response = self.vms_api.delete_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        self.lg.info(' [*] List kvms in python client, (VM0) should be gone')
        vms = self.core0_client.client.kvm.list()
        self.assertNotIn(self.data['id'], [x['name'] for x in vms])

        self.lg.info(' [*] Delete non existing virtual machine, should fail with 404')
        response = self.vms_api.delete_nodes_vms_vmid(self.nodeid, 'fake_vm')
        self.assertEqual(response.status_code, 404)

    def test007_post_nodes_vms_vmid_start_stop(self):
        """ GAT-073
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Stop virtual machine (VM0), should succeed with 204.
        #. Start virtual machine (VM0), should succeed with 204.
        #. Get virtual machine (VM0), virtual machine (VM0) status should be running.
        """
        self.lg.info(' [*] Stop virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_stop(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'halted', "can't stop vm")

        core0_vm_list = self.core0_client.client.kvm.list()
        self.assertNotIn(self.data['id'], [x['name'] for x in core0_vm_list])

        self.lg.info(' [*] Execute command on virtual machine (VM0), should fail')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'ERROR')

        self.lg.info(' [*] Start virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_start(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'running', "can't start vm")

        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed')
        vm_ip_address = self.get_vm_default_ipaddress(self.data['id'])        
        response = self.execute_command_inside_vm(self.ssh_client, vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')

        core0_vm_list = self.core0_client.client.kvm.list()
        self.assertIn(self.data['id'], [x['name'] for x in core0_vm_list])


    def test009_post_nodes_vms_vmid_pause_resume(self):
        """ GAT-075
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Pause virtual machine (VM0), should succeed with 204.
        #. Get virtual machine (VM0), virtual machine (VM0) status should be paused.
        #. Resume virtual machine (VM0), should succeed with 204.
        #. Get virtual machine (VM0), virtual machine (VM0) status should be running
        """
        self.lg.info(' [*] Pause virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_pause(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        self.lg.info(' [*] Get virtual machine (VM0), virtual machine (VM0) status should be paused')
        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'paused', "can't pause vm")
         
        core0_list_vms = self.core0_client.client.kvm.list()
        target_vm = [x for x in core0_list_vms if x['name'] == self.data['id']]
        self.assertNotEqual(target_vm, [])
        self.assertEquals(target_vm[0]['state'], 'paused')

        self.lg.info(' [*] Execute command on virtual machine (VM0), should fail')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'ERROR')

        self.lg.info(' [*] Resume virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_resume(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        self.lg.info(' [*] Get virtual machine (VM0), virtual machine (VM0) status should be running')
        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'running', "can't resume vm")

        core0_list_vms = self.core0_client.client.kvm.list()
        target_vm = [x for x in core0_list_vms if x['name'] == self.data['id']]
        self.assertNotEqual(target_vm, [])
        self.assertEquals(target_vm[0]['state'], 'running')

        self.lg.info(' [*] Execute command on virtual machine (VM0), should succeed')
        vm_ip_address = self.get_vm_default_ipaddress(self.data['id'])        
        response = self.execute_command_inside_vm(self.ssh_client, vm_ip_address, 'uname')
        self.assertEqual(response.state, 'SUCCESS')
        self.assertEqual(response.stdout.strip(), 'Linux')


    @unittest.skip('https://github.com/zero-os/0-orchestrator/issues/994')
    def test010_post_nodes_vms_vmid_shutdown(self):
        """ GAT-076
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Shutdown virtual machine (VM0), should succeed with 204.
        #. Get virtual machine (VM0), virtual machine (VM0) status should be halted.
        """
        self.lg.info(' [*] Shutdown virtual machine (VM0), should succeed with 204')
        response = self.vms_api.post_nodes_vms_vmid_shutdown(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 204)

        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'halted', "can't shutdown vm")

        core0_list_vms = self.core0_client.client.kvm.list()
        self.assertNotIn(self.data['id'], [x['name'] for x in core0_list_vms])

        elf.lg.info(' [*] Execute command on virtual machine (VM0), should fail')
        response = self.execute_command_inside_vm(self.ssh_client, self.vm_ip_address, 'uname')
        self.assertEqual(response.state, 'ERROR')


    def test011_post_nodes_vms_vmid_migrate(self):
        """ GAT-077
        **Test Scenario:**

        #. Get random nodid (N0).
        #. Create virtual machine (VM0) on node (N0).
        #. Migrate virtual machine (VM0) to another node, should succeed with 204.
        #. Get virtual machine (VM0), virtual machine (VM0) status should be migrating.
        #. check that the node, VM0 moved to, is cleaned up
        """
        self.lg.info(' [*] List nodes.')
        response = self.nodes_api.get_nodes()
        self.assertEqual(response.status_code, 200)

        if len(self.nodes_info) < 2:
            self.skipTest('need at least 2 nodes')

        self.lg.info(' [*] Migrate virtual machine (VM0) to another node, should succeed with 204')
        new_node = self.get_random_node(except_node=self.nodeid)

        body = {"nodeid": new_node}
        try:
            response = self.vms_api.post_nodes_vms_vmid_migrate(self.nodeid, self.data['id'], body)
        except Exception as e:
            self.fail(e.args)

        self.assertEqual(response.status_code, 204)

        time.sleep(30)

        response = self.vms_api.get_nodes_vms(new_node)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.data['id'], [x['id'] for x in response.json()])

        response = self.vms_api.get_nodes_vms_vmid(new_node, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'running')

        response = self.vms_api.get_nodes_vms(self.nodeid)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.data['id'], [x['id'] for x in response.json()])

        new_node_ip = [x['ip'] for x in self.nodes_info if x['id'] == new_node]
        self.assertNotEqual(new_node_ip, [])

        new_core0_client = Client(new_node_ip[0], password=self.jwt)
        vms = new_core0_client.client.kvm.list()
        self.assertIn(self.data['id'], [x['name'] for x in vms])

        self.lg.info('check that the node, VM0 moved to, is cleaned up')
        res = new_core0_client.client.bash('ps -a | grep "sshd.config"').get()
        self.assertNotIn(self.data['id'], res.stdout)
        res = new_core0_client.client.bash('ls /tmp').get()
        self.assertNotIn(self.data['id'], res.stdout)
        res = new_core0_client.client.bash(
            "netstat -lnt | awk 'NR>2{print $4}' | grep -E ':' | sed 's/.*://' | sort -n | uniq").get()
        self.assertNotIn('400', res.stdout)

    def test012_create_two_vms_with_same_vdisk(self):
        """ GAT-077
        **Test Scenario:**
        
        #. Get random nodid (N0).
        #. Create (VM1) on node (N0) and attach vdisk (VD1) to it. should succeed.
        #. Create (VM2) and attach vdisk (VD1) to it. should fail.
        #. Stop (VM1), should succeed.
        #. Create (VM3) and attach vdisk (VD1) to it. should fail.
        """

        self.lg.info("Create VM2 and attach vdisk VD1 to it. should fail")
        response, data = self.vms_api.post_nodes_vms(node_id=self.nodeid, memory=1024, cpu=1, disks=self.disks)
        self.assertEqual(response.status_code, 400, response.content)

        self.lg.info("Stop VM1, should succeed")
        response = self.vms_api.post_nodes_vms_vmid_stop(nodeid=self.nodeid, vmid=self.data['id'])
        self.assertEqual(response.status_code, 204, response.content)

        response = self.vms_api.get_nodes_vms_vmid(self.nodeid, self.data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'halted', "[*] Can't stop VM")

        self.lg.info("Create VM3 and attach vdisk VD1 to it. should fail")
        response, data = self.vms_api.post_nodes_vms(node_id=self.nodeid, memory=1024, cpu=1, disks=self.disks)
        self.assertEqual(response.status_code, 400, response.content)
