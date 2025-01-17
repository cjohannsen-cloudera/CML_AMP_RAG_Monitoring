// Code generated by go-swagger; DO NOT EDIT.

package models

// This file was generated by the swagger tool.
// Editing this file might prove futile when you re-run the swagger generate command

import (
	"context"

	"github.com/go-openapi/strfmt"
	"github.com/go-openapi/swag"
)

// MetricListFilter metric list filter
//
// swagger:model MetricListFilter
type MetricListFilter struct {

	// The Experiment ID to filter on
	ExperimentID string `json:"experiment_id,omitempty"`

	// The metric names to filter on
	MetricNames []string `json:"metric_names"`

	// The Experiment Run IDs to filter on
	RunIds []string `json:"run_ids"`
}

// Validate validates this metric list filter
func (m *MetricListFilter) Validate(formats strfmt.Registry) error {
	return nil
}

// ContextValidate validates this metric list filter based on context it is used
func (m *MetricListFilter) ContextValidate(ctx context.Context, formats strfmt.Registry) error {
	return nil
}

// MarshalBinary interface implementation
func (m *MetricListFilter) MarshalBinary() ([]byte, error) {
	if m == nil {
		return nil, nil
	}
	return swag.WriteJSON(m)
}

// UnmarshalBinary interface implementation
func (m *MetricListFilter) UnmarshalBinary(b []byte) error {
	var res MetricListFilter
	if err := swag.ReadJSON(b, &res); err != nil {
		return err
	}
	*m = res
	return nil
}
