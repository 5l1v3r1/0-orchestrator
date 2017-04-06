package node

import (
	"encoding/json"
	"net/http"

	"github.com/g8os/go-client"
	"github.com/g8os/grid/api/tools"
)

// PingNode is the handler for POST /node/{nodeid}/ping
// Ping this node
func (api NodeAPI) PingNode(w http.ResponseWriter, r *http.Request) {
	var respBody bool
	cl, err := tools.GetConnection(r,api)
	if err != nil {
		tools.WriteError(w, http.StatusInternalServerError, err)
		return
	}

	core := client.Core(cl)

	if err := core.Ping(); err != nil {
		respBody = false
	} else {
		respBody = true
	}

	json.NewEncoder(w).Encode(&respBody)
}
