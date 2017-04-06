package node

import (
	"encoding/json"
	"net/http"
	"sync"

	log "github.com/Sirupsen/logrus"
	"github.com/g8os/grid/api/tools"
)

// GetStoragePools is the handler for GET /node/{nodeid}/storagepool
// List storage pools present in the node
func (api NodeAPI) GetStoragePools(w http.ResponseWriter, r *http.Request) {

	services, _, err := api.AysAPI.Ays.ListServicesByRole("storagepool", api.AysRepo, nil, nil)
	if err != nil {
		log.Errorf("Error listing storagepool services : %+v", err)
		tools.WriteError(w, http.StatusInternalServerError, err)
		return
	}

	// grab all service details concurently
	wg := sync.WaitGroup{}
	var respBody = make([]StoragePoolListItem, len(services), len(services))
	wg.Add(len(services))

	for i, service := range services {
		go func(name string, i int) {
			defer wg.Done()

			schema, err := api.getServiceDetail(name)
			if err != nil {
				log.Errorf("Error getting detail for storgepool %s : %+v\n", name, err)
				return
			}

			respBody[i] = StoragePoolListItem{
				Status:   schema.Status,
				Capacity: schema.FreeCapacity,
				Name:     name,
			}
		}(service.Name, i)
	}

	wg.Wait()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(&respBody)
}

type storagePoolSchema struct {
	Status       EnumStoragePoolListItemStatus `json:"status"`
	FreeCapacity uint64                        `json:"freeCapacity"`
}

func (api NodeAPI) getServiceDetail(name string) (*storagePoolSchema, error) {
	log.Debugf("Get schema detail for storagepool %s\n", name)

	service, _, err := api.AysAPI.Ays.GetServiceByName(name, "storagepool", api.AysRepo, nil, nil)
	if err != nil {
		return nil, err
	}

	schema := storagePoolSchema{}
	if err := json.Unmarshal(service.Data, &schema); err != nil {
		return nil, err
	}

	return &schema, nil
}
