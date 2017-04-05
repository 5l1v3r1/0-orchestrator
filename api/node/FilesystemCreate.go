package node

import (
	"gopkg.in/validator.v2"
)

// Arguments to create a new filesystem
type FilesystemCreate struct {
	Name  string `json:"name" validate:"nonzero"`
	Quota uint32 `json:"quota" validate:"nonzero"`
}

func (s FilesystemCreate) Validate() error {

	return validator.Validate(s)
}
