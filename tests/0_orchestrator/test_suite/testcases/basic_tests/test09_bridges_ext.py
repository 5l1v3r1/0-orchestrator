import time
from testcases.testcases_base import TestcasesBase


class TestBridgesAPI(TestcasesBase):
    def setUp(self):
        super(TestBridgesAPI, self).setUp()
        self.created = {'bridge': [], 'container': []}

    def tearDown(self):
        self.lg.info('TearDown:delete all created containers and bridges')
        for container_name in self.created['container']:
            self.containers_api.delete_containers_containerid(self.nodeid, container_name)
        for bridge_name in self.created['bridge']:
            self.bridges_api.delete_nodes_bridges_bridgeid(self.nodeid, bridge_name)

    def test001_create_bridges_with_same_name(self):
        """ GAT-101
        *Create two bridges with same name *

        **Test Scenario:**

        #. Create bridge (B1) , should succeed .
        #. Check that created bridge exist in bridges list.
        #. Create bridge (B2) with same name for (B1),should fail.
        #. Delete bridge (B1), should succeed.

        """
        self.lg.info(' [*] Create bridge (B1) , should succeed .')
        response, data_bridge_1 = self.bridges_api.post_nodes_bridges(node_id=self.nodeid)
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge_1['name'])

        self.lg.info(" [*] Check that created bridge exist in bridges list.")
        response = self.bridges_api.get_nodes_bridges(self.nodeid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue([x for x in response.json() if x["name"] == data_bridge_1['name']])

        self.lg.info(' [*] Create bridge (B2) with same name for (B1),should fail.')
        response, data_bridge_2 = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, name=data_bridge_1['name'])
        self.assertEqual(response.status_code, 409, response.content)

    def test002_create_bridge_with_nat(self):
        """ GAT-102
        *Create bridge with nat options *

        **Test Scenario:**

        #. Create bridge (B0) with false in nat option,should succeed.
        #. Create container (C0) with (B0) bridge,should succeed.
        #. Check that C0 can connect to internet ,should fail.
        #. Create bridge (B1) with true in nat option , should succed.
        #. Create container(C1) with (B1) bridge ,should succeed.
        #. Check that (C1) can connect to internet ,should succeed.

        """
        self.lg.info(' [*] Create bridge (B1) , should succeed .')
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='dnsmasq',
                                                                    nat=False)
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge['name'])

        self.lg.info(' [*] Create container(C1) with (B1), should succeed.')
        nics = [{"type": "bridge", "id": data_bridge['name'], "config": {"dhcp": True}, "status": "up"}]
        response_c1, data_c1 = self.containers_api.post_containers(nodeid=self.nodeid, nics=nics)
        self.assertEqual(response_c1.status_code, 201)
        self.created['container'].append(data_c1['name'])

        c_client = self.core0_client.get_container_client(data_c1['name'])

        if not data_bridge['nat']:
            self.lg.info(' [*] Check that C can connect to internet ,should fail.')
            response = c_client.bash("ping -c1 8.8.8.8").get()
            self.assertEqual(response.state, "ERROR", response.stdout)
        else:
            self.lg.info(' [*] Check that C can connect to internet ,should succeed.')
            response = c_client.bash("ping -c1 8.8.8.8").get()
            self.assertEqual(response.state, "SUCCESS", response.stdout)

    def test003_create_bridge_with_hwaddr(self):
        """ GAT-103
        *Create bridge with hardware address *

        **Test Scenario:**

        #. Create bridge (B0) with specefic hardware address,should succeed.
        #. Check that bridge created with this hardware address, should succeed.
        #. Create bridge (B1) with wrong hardware address, should fail.

        """
        self.lg.info(' [*] Create bridge (B1) , should succeed .')
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid)
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge['name'])

        self.lg.info(" [*]  Check that bridge(B0) created with this hardware address, should succeed.")
        response = self.nodes_api.get_nodes_nodeid_nics(self.nodeid)
        self.assertEqual(response.status_code, 200)
        nic = [x for x in response.json() if x["name"] == data_bridge['name']][0]
        self.assertEqual(nic["hardwareaddr"], data_bridge['hwaddr'])

        self.lg.info(" [*] Create bridge (B1) with wrong hardware address, should fail.")
        hardwareaddr = self.rand_str()
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, hwaddr=hardwareaddr)
        self.assertEqual(response.status_code, 400, response.content)

    def test004_create_bridge_with_static_networkMode(self):
        """ GAT-104
        *Create bridge with static network mode *

        **Test Scenario:**

        #. Create bridge (B0), should succeed.
        #. Check that (B0)bridge took given cidr address, should succeed.

        """
        self.lg.info(" [*]  Create bridge (B0), should succeed.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static')
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge['name'])

        self.lg.info(" [*] Check that (B0)bridge took given cidr address, should succeed.")
        response = self.nodes_api.get_nodes_nodeid_nics(self.nodeid)
        self.assertEqual(response.status_code, 200)
        nic = [x for x in response.json() if x["name"] == data_bridge['name']][0]
        self.assertIn(data_bridge['hwaddr'], nic["hardwareaddr"])

    def test005_create_bridges_with_static_networkMode_and_same_cidr(self):
        """ GAT-105
        *Create two bridges with static network mode and same cidr address *

        **Test Scenario:**

        #. Create bridge (B0), should succeed.
        #. Check that created bridge exist in bridges list.
        #. Create bridge(B1) with same cidr as (B0),should fail.

        """
        self.lg.info(" [*]  Create bridge (B0), should succeed.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static')
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge['name'])

        self.lg.info(" [*] Check that created bridge exist in bridges list.")
        response = self.bridges_api.get_nodes_bridges(self.nodeid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue([x for x in response.json() if x["name"] == data_bridge['name']])

        self.lg.info(" [*] Create bridge(B1)with same cidr as (B0),should fail.")
        response, data_bridge_2 = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static',
                                                                      setting=data_bridge['setting'])
        self.assertEqual(response.status_code, 409, response.content)

    def test006_create_bridge_with_invalid_cidr_in_static_networkMode(self):
        """ GAT-106
        *Create bridge with static network mode and invalid cidr address  *

        **Test Scenario:**

        #. Create bridge (B) with invalid cidr address, should fail.

        """

        self.lg.info(" [*]  Create bridge (B) with invalid cidr address, should fail..")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static',
                                                                    setting={"cidr": "260.120.3.1/8"})
        self.assertEqual(response.status_code, 400, response.content)

    def test007_create_bridge_with_empty_setting_in_static_networkMode(self):
        """ GAT-107
        *Create bridge with static network mode and invalid empty cidr address. *

        **Test Scenario:**

        #. Create bridge (B) with static network mode and empty cidr value,should fail.

        """

        self.lg.info(" [*]  Create bridge (B) with static network mode and empty cidr value,should fail.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static',
                                                                    setting={})
        self.assertEqual(response.status_code, 400, response.content)

    def test008_create_bridge_with_dnsmasq_networkMode(self):
        """ GAT-108
        *Create bridge with dnsmasq network mode *

        **Test Scenario:**

        #. Create bridge (B) with dnsmasq network mode, should succeed.
        #. Check that (B)bridge took given cidr address, should succeed.

        """
        self.lg.info(" [*]  Create bridge (B0), should succeed.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='dnsmasq')
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge['name'])

        self.lg.info(" [*] Check that (B) bridge took given cidr address, should succeed.")
        response = self.nodes_api.get_nodes_nodeid_nics(self.nodeid)
        self.assertEqual(response.status_code, 200)
        nic = [x for x in response.json() if x["name"] == data_bridge['name']][0]
        self.assertIn(data_bridge['hwaddr'], nic["hardwareaddr"])

    def test009_create_bridges_with_dnsmasq_networkMode_and_overlapping_cidrs(self):
        """ GAT-109
        *Create bridges with dnsmasq network mode and overlapping cidrs. *

        **Test Scenario:**

        #. Create bridge (B0) with dnsmasq network mode, should succeed.
        #. Check that created bridge exist in bridges list.
        #. Create bridge (B1) overlapping with (B0) cidr address,shoud fail.

        """
        self.lg.info(" [*]  Create bridge (B0), should succeed.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static')
        self.assertEqual(response.status_code, 201, response.content)
        self.created['bridge'].append(data_bridge['name'])

        self.lg.info(" [*] Check that created bridge exist in bridges list.")
        response = self.bridges_api.get_nodes_bridges(self.nodeid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue([x for x in response.json() if x["name"] == data_bridge['name']])

        self.lg.info(" [*]  Create bridge (B1) overlapping with (B0) address, should fail.")
        response, data_bridge_2 = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='static',
                                                                      setting=data_bridge['setting'])
        self.assertEqual(response.status_code, 409, response.content)

    def test010_create_bridge_with_out_of_range_address_in_dnsmasq(self):
        """ GAT-110
        *Create bridge with dnsmasq network mode and out of range start and end values *

        **Test Scenario:**

        #. Create bridge(B) with out of range start and end values, shoud fail.

        """

        self.lg.info(" [*] Create bridge(B) with out of range start and end values, should fail.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='dnsmasq',
                                                                    setting={"cidr": "192.168.20.1/24",
                                                                             "start": "192.168.50.2",
                                                                             "end": "192.168.50.254"})
        self.assertEqual(response.status_code, 400, response.content)

    def test011_create_bridge_with_invalid_settings_in_dnsmasq(self):
        """ GAT-111
        *Create bridge with dnsmasq network mode and invalid settings. *

        **Test Scenario:**

        #.Create bridge (B0) with dnsmasq network mode and empty setting value,should fail.
        #.Create bridge (B1) with dnsmasq network and empty start and end values, should fail.

        """
        self.lg.info(" [*]  Create bridge (B0) with dnsmasq network mode and empty setting value,should fail.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='dnsmasq',
                                                                    setting={})
        self.assertEqual(response.status_code, 400, response.content)

        self.lg.info(" [*]  Create bridge (B1) with dnsmasq network and empty start and end values, should fail.")
        self.lg.info(" [*] Create bridge(B) with out of range start and end values, should fail.")
        response, data_bridge = self.bridges_api.post_nodes_bridges(node_id=self.nodeid, networkMode='dnsmasq',
                                                                    setting={"cidr": "192.168.20.1/24"})
        self.assertEqual(response.status_code, 400, response.content)
