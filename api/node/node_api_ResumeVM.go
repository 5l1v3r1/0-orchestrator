package node

import (
	"net/http"
)

// ResumeVM is the handler for POST /nodes/{nodeid}/vms/{vmid}/resume
// Resumes the VM
func (api NodeAPI) ResumeVM(w http.ResponseWriter, r *http.Request) {
}
