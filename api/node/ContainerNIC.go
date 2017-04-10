package node

import (
	"gopkg.in/validator.v2"
)

type ContainerNIC struct {
	Config string               `json:"config,omitempty"`
	Hwaddr string               `json:"hwaddr,omitempty"`
	Id     string               `json:"id" validate:"nonzero"`
	Type   EnumContainerNICType `json:"type" validate:"nonzero"`
}

func (s ContainerNIC) Validate() error {

	return validator.Validate(s)
}
