package node

import (
	"gopkg.in/validator.v2"
)

type CreateContainer struct {
	Nics           []ContainerNIC `json:"nics" validate:"nonzero"`
	Filesystems    []string       `json:"filesystems"`
	Flist          string         `json:"flist" validate:"nonzero"`
	HostNetworking bool           `json:"hostNetworking"`
	Hostname       string         `json:"hostname" validate:"nonzero"`
	Id             string         `json:"id" validate:"nonzero"`
	InitProcesses  []CoreSystem   `json:"initProcesses"`
	Ports          []string       `json:"ports"`
	Storage        string         `json:"storage"`
}

func (s CreateContainer) Validate() error {

	return validator.Validate(s)
}
