package storagecluster

//This file is auto-generated by go-raml
//Do not edit this file by hand since it will be overwritten during the next generation

import (
	"github.com/gorilla/mux"
	"net/http"
)

// StorageclusterInterface is interface for /storagecluster root endpoint
type StorageclusterInterface interface { // ListAllClusters is the handler for GET /storagecluster
	// List all running clusters
	ListAllClusters(http.ResponseWriter, *http.Request)
	// DeployNewCluster is the handler for POST /storagecluster
	// Deploy New Cluster
	DeployNewCluster(http.ResponseWriter, *http.Request)
	// GetClusterInfo is the handler for GET /storagecluster/{label}
	// Get full Information about specific cluster
	GetClusterInfo(http.ResponseWriter, *http.Request)
	// KillCluster is the handler for DELETE /storagecluster/{label}
	// Kill cluster
	KillCluster(http.ResponseWriter, *http.Request)
	// CreateNewVolume is the handler for POST /storagecluster/{label}/volumes
	// Create a new volume, can be a copy from an existing volume
	CreateNewVolume(http.ResponseWriter, *http.Request)
	// GetVolumeInfo is the handler for GET /storagecluster/{label}/volumes/{volumeid}
	// Get volume information
	GetVolumeInfo(http.ResponseWriter, *http.Request)
	// DeleteVolume is the handler for DELETE /storagecluster/{label}/volumes/{volumeid}
	// Delete Volume
	DeleteVolume(http.ResponseWriter, *http.Request)
	// ResizeVolume is the handler for POST /storagecluster/{label}/volumes/{volumeid}/resize
	// Resize Volume
	ResizeVolume(http.ResponseWriter, *http.Request)
	// RollbackVolume is the handler for POST /storagecluster/{label}/volumes/{volumeid}/rollback
	// Rollback a volume to a previous state
	RollbackVolume(http.ResponseWriter, *http.Request)
}

// StorageclusterInterfaceRoutes is routing for /storagecluster root endpoint
func StorageclusterInterfaceRoutes(r *mux.Router, i StorageclusterInterface) {
	r.HandleFunc("/storagecluster", i.ListAllClusters).Methods("GET")
	r.HandleFunc("/storagecluster", i.DeployNewCluster).Methods("POST")
	r.HandleFunc("/storagecluster/{label}", i.GetClusterInfo).Methods("GET")
	r.HandleFunc("/storagecluster/{label}", i.KillCluster).Methods("DELETE")
	r.HandleFunc("/storagecluster/{label}/volumes", i.CreateNewVolume).Methods("POST")
	r.HandleFunc("/storagecluster/{label}/volumes/{volumeid}", i.GetVolumeInfo).Methods("GET")
	r.HandleFunc("/storagecluster/{label}/volumes/{volumeid}", i.DeleteVolume).Methods("DELETE")
	r.HandleFunc("/storagecluster/{label}/volumes/{volumeid}/resize", i.ResizeVolume).Methods("POST")
	r.HandleFunc("/storagecluster/{label}/volumes/{volumeid}/rollback", i.RollbackVolume).Methods("POST")
}
