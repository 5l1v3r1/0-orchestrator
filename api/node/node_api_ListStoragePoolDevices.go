package node

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"

	log "github.com/Sirupsen/logrus"

	client "github.com/g8os/go-client"
	"github.com/g8os/grid/api/tools"
	"github.com/gorilla/mux"
)

// Get storage pool service data, of the same node
// Get the devices list from their data
// if empty make it empty slice
// From the text get data u needed for
//  Handle errors from all

// ListStoragePoolDevices is the handler for GET /nodes/{nodeid}/storagepools/{storagepoolname}/devices
// Lists the devices in the storage pool
func (api NodeAPI) ListStoragePoolDevices(w http.ResponseWriter, r *http.Request) {
	var respBody []StoragePoolDevice

	vars := mux.Vars(r)
	storagepoolname := vars["storagepoolname"]
	nodeid := vars["nodeid"]

	devices, err := api.getStoragePoolDevices(nodeid, storagepoolname)
	if err != nil {
		log.Errorf("Error Listing storage pool devices: %+v", err)
		tools.WriteError(w, http.StatusInternalServerError, err)
		return
	}

	cl, err := tools.GetConnection(r, api)
	if err != nil {
		log.Errorf("Error Listing storage pool devices: %+v", err)
		tools.WriteError(w, http.StatusInternalServerError, err)
		return
	}

	core := client.Core(cl)
	res, err := core.ListStoragePoolDevices(devices)
	if err != nil {
		log.Errorf("Error Listing storage pool devices: %+v", err)
		tools.WriteError(w, http.StatusInternalServerError, err)
		return
	}

	for _, dev := range res {
		for _, info := range dev.Devices {
			if str, ok := info["path"].(string); ok {
				if containsStrings(devices, str) {
					respBody = append(respBody, StoragePoolDevice{Uuid: dev.UUID})
				}
			}
		}
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(&respBody)
}

// Get storagepool devices
func (api NodeAPI) getStoragePoolDevices(node, storagepool string) ([]string, error) {
	queryParams := map[string]interface{}{"parent": fmt.Sprintf("node.g8os!%s", node)}

	service, _, err := api.AysAPI.Ays.GetServiceByName(storagepool, "storagepool", api.AysRepo, nil, queryParams)
	if err != nil {
		return nil, err
	}

	var data struct {
		Devices []string `json:"devices"`
	}
	if err := json.Unmarshal(service.Data, &data); err != nil {
		log.Errorf("Error Unmarshal storagepool service '%s' data: %+v", storagepool, err)
		return nil, err
	}

	return data.Devices, nil
}

func containsStrings(slice []string, target string) bool {
	sort.Strings(slice)
	i := sort.SearchStrings(slice, target)
	if i < len(slice) && slice[i] == target {
		return true
	}
	return false
}
