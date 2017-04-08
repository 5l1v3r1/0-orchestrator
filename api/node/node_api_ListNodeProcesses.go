package node

import (
	"encoding/json"
	"net/http"
)

// ListNodeProcesses is the handler for GET /nodes/{nodeid}/processes
// Get Processes
func (api NodeAPI) ListNodeProcesses(w http.ResponseWriter, r *http.Request) {
	var respBody []Process
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(&respBody)

}
