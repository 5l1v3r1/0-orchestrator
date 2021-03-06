package node

import (
	"net/http"

	"github.com/gorilla/mux"
	"github.com/zero-os/0-orchestrator/api/tools"
)

// DeleteStoragePool is the handler for DELETE /node/{nodeid}/storagepool/{storagepoolname}
// Delete the storage pool
func (api *NodeAPI) DeleteStoragePool(w http.ResponseWriter, r *http.Request) {
	aysClient, err := tools.GetAysConnection(api)
	if err != nil {
		tools.WriteError(w, http.StatusUnauthorized, err, "")
		return
	}
	vars := mux.Vars(r)
	name := vars["storagepoolname"]

	// execute the delete action of the snapshot
	blueprint := map[string]interface{}{
		"actions": []tools.ActionBlock{{
			Action:  "delete",
			Actor:   "storagepool",
			Service: name,
			Force:   true,
		}},
	}

	run, err := aysClient.ExecuteBlueprint(api.AysRepo, "storagepool", name, "delete", blueprint)
	errmsg := "Error executing blueprint for storagepool deletion "
	if !tools.HandleExecuteBlueprintResponse(err, w, errmsg) {
		return
	}

	// Wait for the delete job to be finshed before we delete the service
	if _, err = aysClient.WaitRunDone(run.Key, api.AysRepo); err != nil {
		httpErr, ok := err.(tools.HTTPError)
		if ok {
			tools.WriteError(w, httpErr.Resp.StatusCode, httpErr, "Error running blueprint for storagepool deletion")
		} else {
			tools.WriteError(w, http.StatusInternalServerError, err, "Error running blueprint for storagepool deletion")
		}
		return
	}

	res, err := aysClient.Ays.DeleteServiceByName(name, "storagepool", api.AysRepo, nil, nil)
	if !tools.HandleAYSDeleteResponse(err, res, w, "deleting service") {
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
