# Resource Pool Development Setup

All steps:
1. Create a ZeroTier network
2. [Setup the AYS Server](#ays-server)
3. [Setup the Resource Pool Server](#resourcepool-api)
4. [Start the Bootstrap Service, using an AYS blueprint](#bootstrap-service)
5. [Boot the G8OS nodes](#boot-nodes)

The first step is pretty straight forward, go to https://my.zerotier.com/ and create your ZeroTier network.

For the next 3 steps you have two options:
- Do it all manually as documented here below in the linked sections
- Or run the AYS Server, the Resource Pool Server and the Bootstrap service in a Docker container, leveraging two bash scripts that automate all this

The automated setup is documented below in the two first sections:
- [Create and start the Docker container](#docker-container)
- [Starting AYS, the API Server and the bootstrap service](#start-services)

The last step is documented in [Boot your G8OS nodes](#boot-nodes).

<a id="docker-container"></a>
## Create and start the Docker container

On your machine where you plan to host the Docker container:
```
curl -sL https://raw.githubusercontent.com/Jumpscale/developer/master/scripts/js_builder_js82_zerotier.sh | bash -s <your-ZeroTier-network-ID>
```

To see interactive output do the following in a separate console:
```
tail -f /tmp/lastcommandoutput.txt
```

For more details about using using `js_builder_js82_zerotier.sh` see [here](https://github.com/Jumpscale/developer/blob/master/docs/installjs8_details.md).


<a id="start-services"></a>
## Starting AYS, the API Server and the bootstrap service

From your machine, hosting the Docker container:
```
curl -sL https://raw.githubusercontent.com/Jumpscale/developer/master/scripts/g8os_grid_installer82.sh | bash -s <Branch> <your-ZeroTier-network-ID> <your-ZeroTier-Token>
```

Again, to see interactive output do the following in separate console:
```
tail -f /tmp/lastcommandoutput.txt
```

Next step is to boot the G8OS nodes, documented in [Create the G8OS nodes](#create-nodes), the last section on this page.


<a id="ays-server"></a>
## Setup the AYS server

* Install JumpScale

  On the machine where you want to run the AYS Server execute:

  ```shell
  cd $TMPDIR
  rm -f install.sh
  export JSBRANCH="8.2.0"
  curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/$JSBRANCH/install/install.sh?$RANDOM > install.sh
  bash install.sh
  ```

  For more details on installing JumpScale see the [JumpScale documentation](https://gig.gitbooks.io/jumpscale-core8/content/Installation/JSDevelopment.html).

* Install the Python client

  `g8core` is the Python client that AYS uses to interact with a G8OS node.

  In order to install it execute:

  ```shell
  pip3 install g8core
  ```

* Install ZeroTier Python client

```shell
pip3 install zerotier
```

* Get the AYS actor templates for setting up a resource pool

  The AYS actor templates for setting up all the resource pool server components are available in the `templates` directory of the resource pool server repository on GitHub.

  In order to clone this repository execute:

  ```shell
  cd /opt/code/
  git clone https://github.com/g8os/resourcepool/
  cd resourcepool
  git checkout 1.1.0-alpha
  ```

* Start the AYS server

  Execute:
  ```shell
  ays start
  ```

* Create a new AYS repository

  This is the AYS repository that you will use for the blueprints to setup the resource pool.

  ```shell
  ays repo create --name {repo-name} --git {git-server}
  ```

  Values:
  - **{repo-name}**: Any name you choose for your AYS repository
  - **{git-server}**: https address of your repository on a Git server, e.g. `http://github.com/user/repo`


<a id="resourcepool-api"></a>
## Setup the resource pool API server

  * Build the resource pool API server

    If not already done before, first clone the resource pool server repository, and then build the server:

    ```shell
    git clone https://github.com/g8os/resourcepool
    cd resourcepool/api
    git checkout 1.1.0-alpha
    go build
    ```

  * Run the resource pool API server

    Execute:

    `./api --bind :8080 --ays-url http://localhost:5000 --ays-repo {repo-name}`

    Options:
    - `--bind :8080` makes the server listen on all interfaces on port 8080
    - `--ays-url` needed to point to the AYS REST API
    - `--ays-repo` is the name of the AYS repository the resource pool API need to use. It should be the repo you created in step 1.

<a id="bootstrap-service"></a>
## Install the auto node discovery service

      Add the following blueprint in the `blueprints` directory of your AYS repository:

      ```
      bootstrap.g8os__resourcepool1:
        zerotierNetID: {ZeroTier-Network-ID}
        zerotierToken: '{ZeroTier-API-Token}'

      actions:
        - action: install
      ```

      Values:
      - **{ZeroTier-Network-ID}**: a ZeroTier Network ID
      - **{ZeroTier-API-Token}**: a ZeroTier API Access Token

      You get both values from the ZeroTier web portal: https://my.zerotier.com/

      This blueprint will install the **auto discovery service** which will auto discover all G8OS nodes that were setup to connect to the same ZeroTier network.

      Alternatively you can also manually add a G8OS node to the resource pool with following blueprint:

      ```
      node.g8os__525400123456:
        redisAddr: 172.17.0.1

      actions:
       - action: install
      ```

      In the above example `525400123456` is the MAC address of the G8OS node with the ':' removed and the `redisAddr` is the IP address of the node.

      After creating both blueprints, run the following commands to execute the blueprints and have the actions executed:

      ```shell
      ays blueprint
      ays run create --follow
      ```

<a id="boot-nodes"></a>
## Create the G8OS nodes

Download your iPXE boot ISO image from the G8OS bootstrap service: https://bootstrap.gig.tech/iso/${BRANCH}/${ZeroTier-Network-ID}

Use this image to boot your node. For all detailed instruction on how to boot a G8OS node see the Core0 documentation: https://github.com/g8os/core0
