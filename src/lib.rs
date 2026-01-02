use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use pyo3::types::PyBytes;
use arrow::pyarrow::ToPyArrow;
use arrow::datatypes::{FieldRef, Schema};
use arrow::array::RecordBatch;
use serde_json::Value as JsonValue; // Keep for fallback if needed, but we try not to use it
use serde_arrow::schema::{SchemaLike, TracingOptions};
use std::sync::Arc;
use serde::{Serialize, Serializer};
use cbor4ii::core::{Value, utils::SliceReader, dec::Decode};

/// Wrapper around cbor4ii::core::Value to implement custom Serialize logic
/// specifically for SurrealDB types like RecordID (Tag 8).
#[derive(Debug, Clone)]
struct SurrealValue(Value);

impl Serialize for SurrealValue {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match &self.0 {
            Value::Null => serializer.serialize_none(),
            Value::Bool(b) => serializer.serialize_bool(*b),
            Value::Integer(i) => {
                 let v = *i; // i128
                 // Optimize for smaller ints
                 if let Ok(v64) = i64::try_from(v) {
                     return serializer.serialize_i64(v64);
                 }
                 if let Ok(u64_val) = u64::try_from(v) {
                     return serializer.serialize_u64(u64_val);
                 }
                 serializer.serialize_i128(v)
            }
            Value::Float(f) => serializer.serialize_f64(*f),
            Value::Bytes(b) => serializer.serialize_bytes(b),
            Value::Text(s) => serializer.serialize_str(s),
            Value::Array(arr) => {
                use serde::ser::SerializeSeq;
                let mut seq = serializer.serialize_seq(Some(arr.len()))?;
                for element in arr {
                    seq.serialize_element(&SurrealValue(element.clone()))?;
                }
                seq.end()
            }
            Value::Map(map) => {
                use serde::ser::SerializeMap;
                let mut m = serializer.serialize_map(Some(map.len()))?;
                for (k, v) in map {
                    // keys in CBOR can be any type, but JSON/Arrow expects string keys usually.
                    // stringify key if not string
                    let key_str = match k {
                        Value::Text(s) => s.clone(),
                        _ => format!("{:?}", k),
                    };
                    m.serialize_entry(&key_str, &SurrealValue(v.clone()))?;
                }
                m.end()
            }
            Value::Tag(tag, value) => {
                if *tag == 8 {
                    // RecordID: Table:ID
                    // Usually value is Array(2) [table, id] (both strings/text)
                    if let Value::Array(arr) = value.as_ref() {
                        if arr.len() == 2 {
                             let table = match &arr[0] {
                                 Value::Text(s) => s,
                                 _ => "",
                             };
                             let id = match &arr[1] {
                                 Value::Text(s) => s,
                                 Value::Integer(i) => return serializer.serialize_str(&format!("{}:{}", table, i)),
                                 _ => "",
                             };
                             return serializer.serialize_str(&format!("{}:{}", table, id));
                        }
                    }
                }
                // Fallback for other tags: ignore tag, serialize value
                SurrealValue(*value.clone()).serialize(serializer)
            }
            _ => serializer.serialize_unit(), // Simple/Msg?
        }
    }
}

/// Formats the sum of two numbers as string.
#[pyfunction]
fn sum_as_string(a: usize, b: usize) -> PyResult<String> {
    Ok((a + b).to_string())
}

/// Convert CBOR bytes to an Arrow RecordBatch (as a PyArrow Table/batch).
#[pyfunction]
fn cbor_to_arrow(py: Python, data: &Bound<'_, PyBytes>) -> PyResult<PyObject> {
    let bytes = data.as_bytes();

    // 1. Decode to cbor4ii::core::Value (Low level)
    let mut reader = SliceReader::new(bytes);
    
    // cbor4ii 0.3.x: Value::decode(&mut reader)
    let root: Value = Value::decode(&mut reader)
         .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("CBOR decode error: {:?}", e)))?;

    // 2. Extract inner data
    // Path: root -> "result" (Array) -> [0] -> "result" (Array of records)
    let records_values_opt = if let Value::Map(ref map) = root {
        map.iter()
            .find(|(k, _)| matches!(k, Value::Text(s) if s == "result"))
            .and_then(|(_, v)| {
                 if let Value::Array(arr) = v {
                     arr.get(0)
                 } else { None }
            })
            .and_then(|v| {
                 if let Value::Map(map) = v {
                      map.iter()
                        .find(|(k, _)| matches!(k, Value::Text(s) if s == "result"))
                        .map(|(_, v)| v)
                 } else { None }
            })
    } else {
        None
    };

    let records_arr = match records_values_opt {
        Some(Value::Array(arr)) => arr,
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("Could not find 'result[0].result' array in CBOR response")),
    };

    if records_arr.is_empty() {
        return Ok(py.None());
    }

    // 3. Wrap in SurrealValue
    let wrapped_records: Vec<SurrealValue> = records_arr.iter()
        .map(|v| SurrealValue(v.clone()))
        .collect();

    // 4. Infer Schema
    let fields = Vec::<FieldRef>::from_samples(&wrapped_records, TracingOptions::default())
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Schema inference error: {}", e)))?;

    // 5. Convert
    let arrays = serde_arrow::to_arrow(&fields, &wrapped_records)
         .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Arrow array conversion error: {}", e)))?;

    // 6. Build Batch
    let schema = Arc::new(Schema::new(fields));
    let batch = RecordBatch::try_new(schema, arrays)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("RecordBatch creation error: {}", e)))?;

    batch.to_pyarrow(py)
}

/// A Python module implemented in Rust.
#[pymodule]
fn surrealengine_accelerator(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_as_string, m)?)?;
    m.add_function(wrap_pyfunction!(cbor_to_arrow, m)?)?;
    Ok(())
}
