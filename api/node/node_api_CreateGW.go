package node

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/g8os/resourcepool/api/tools"
	"github.com/gorilla/mux"
)

type CreateGWBP struct {
	Node         string        `json:"node" yaml:"node"`
	Domain       string        `json:"domain" yaml:"domain"`
	Nics         []GWNIC       `json:"nics" yaml:"nics"`
	Httpproxies  []HTTPProxy   `json:"httpproxies" yaml:"httpproxies"`
	Portforwards []PortForward `json:"portforwards" yaml:"portforwards"`
}

// CreateGW is the handler for POST /nodes/{nodeid}/gws
// Create a new gateway
func (api NodeAPI) CreateGW(w http.ResponseWriter, r *http.Request) {
	var reqBody GWCreate

	vars := mux.Vars(r)
	nodeID := vars["nodeid"]

	// decode request
	if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		return
	}

	// validate request
	if err := reqBody.Validate(); err != nil {
		tools.WriteError(w, http.StatusBadRequest, err)
		return
	}

	gateway := CreateGWBP {
		Node:         nodeID,
		Domain:       reqBody.Domain,
		Nics:         reqBody.Nics,
		Httpproxies:  reqBody.Httpproxies,
		Portforwards: reqBody.Portforwards,
	}

	obj := make(map[string]interface{})
	obj[fmt.Sprintf("gateway__%s", reqBody.Name)] = gateway
	obj["actions"] = []tools.ActionBlock{{Action: "install", Service: reqBody.Name, Actor: "gateway"}}

	if _, err := tools.ExecuteBlueprint(api.AysRepo, "gateway", reqBody.Name, "install", obj); err != nil {
		fmt.Errorf("error executing blueprint for gateway %s creation : %+v", reqBody.Name, err)
		tools.WriteError(w, http.StatusInternalServerError, err)
		return
	}

	w.Header().Set("Location", fmt.Sprintf("/nodes/%s/gws/%s", nodeID, reqBody.Name))
	w.WriteHeader(http.StatusCreated)

}
