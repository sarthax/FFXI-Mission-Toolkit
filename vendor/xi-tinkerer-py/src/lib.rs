use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::path::PathBuf;

use dats::dat_format::DatFormat;
use dats::formats::auto_translate::AutoTranslate;
use dats::formats::dialog::Dialog;
use dats::formats::dmsg_table::DmsgTable;
use dats::formats::entity_names::EntityNames;
use dats::formats::events::Events;
use dats::formats::furniture_data::FurnitureData;
use dats::formats::item_info::ItemInfoTable;
use dats::formats::menu_table::MenuTable;
use dats::formats::status_info::StatusInfoTable;
use dats::formats::xistring_table::XiStringTable;
use dats::formats::zone_data::{ChunkData, ZoneData, math::Vertex, zone_mmb::ZoneMmbModels, zone_model::ZoneMesh};
use std::collections::HashMap;

fn serde_to_pyobject(py: Python, val: &serde_json::Value) -> PyObject {
    match val {
        serde_json::Value::Null => py.None(),
        serde_json::Value::Bool(b) => b.into_pyobject(py).unwrap().to_owned().into_any().unbind(),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_pyobject(py).unwrap().into_any().unbind()
            } else if let Some(f) = n.as_f64() {
                f.into_pyobject(py).unwrap().into_any().unbind()
            } else {
                py.None()
            }
        }
        serde_json::Value::String(s) => s.into_pyobject(py).unwrap().into_any().unbind(),
        serde_json::Value::Array(arr) => {
            let items: Vec<PyObject> = arr.iter().map(|v| serde_to_pyobject(py, v)).collect();
            let list = PyList::new(py, &items).unwrap();
            list.into_pyobject(py).unwrap().into_any().unbind()
        }
        serde_json::Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, serde_to_pyobject(py, v)).unwrap();
            }
            dict.into_pyobject(py).unwrap().into_any().unbind()
        }
    }
}

fn parse_format<T: DatFormat + serde::Serialize>(py: Python, path: &str) -> PyResult<PyObject> {
    let dat_path = PathBuf::from(path);
    let data = T::from_path(&dat_path)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Parse error: {e}")))?;
    let json_val = serde_json::to_value(&data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Serialize error: {e}")))?;
    Ok(serde_to_pyobject(py, &json_val))
}

#[pyfunction]
fn parse_menu_table(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<MenuTable>(py, path)
}

#[pyfunction]
fn parse_dialog(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<Dialog>(py, path)
}

#[pyfunction]
fn parse_dmsg_table(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<DmsgTable>(py, path)
}

#[pyfunction]
fn parse_entity_names(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<EntityNames>(py, path)
}

#[pyfunction]
fn parse_events(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<Events>(py, path)
}

#[pyfunction]
fn parse_item_info(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<ItemInfoTable>(py, path)
}

#[pyfunction]
fn parse_status_info(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<StatusInfoTable>(py, path)
}

#[pyfunction]
fn parse_xistring_table(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<XiStringTable>(py, path)
}

#[pyfunction]
fn parse_auto_translate(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<AutoTranslate>(py, path)
}

#[pyfunction]
fn parse_furniture_data(py: Python, path: &str) -> PyResult<PyObject> {
    parse_format::<FurnitureData>(py, path)
}

fn format_f32(val: f32) -> String {
    format!("{:.3}", val)
        .trim_end_matches('0')
        .trim_end_matches('.')
        .to_string()
}

/// Zone COLLISION mesh (the geometry the client's own navmesh/traversal is built from) as a
/// real Wavefront OBJ string -- adapted from xi-tinkerer's own `processor::wavefront_obj::
/// make_collision_wavefront_file` (same repo, AGPLv3, not a foreign/unlicensed source) so the
/// Mission Toolkit can render a real top-down zone outline that's coordinate-correct against
/// real capture x/y/z by construction (same world-space vertices, no scale/offset guessing --
/// unlike the client's decorative 2D minimap PNGs, which carry no such guarantee).
#[pyfunction]
fn parse_zone_collision_obj(path: &str) -> PyResult<String> {
    let dat_path = PathBuf::from(path);
    let zone_data = ZoneData::from_path(&dat_path)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Parse error: {e}")))?;
    let zone_mesh = ZoneMesh::parse_from_zone_data(&zone_data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("No zone model: {e}")))?;

    let mut out = String::new();
    let mut vertex_count: usize = 1;
    for cell in zone_mesh.mesh.grid_cells.iter() {
        for index in &cell.indices {
            let block = &zone_mesh.mesh.blocks[index.block_idx as usize];
            let placement = &zone_mesh.mesh.placements[index.placement_idx as usize];
            let flip_vertices = placement.o2w.determinant() > 0f32;

            for vertex in &block.vertices {
                let vertex = placement.o2w.apply_to_vertex(vertex);
                out.push_str(&format!(
                    "v {} {} {}\n",
                    format_f32(vertex.x),
                    format_f32(-vertex.y),
                    format_f32(-vertex.z)
                ));
            }

            if flip_vertices {
                for tri in &block.triangles {
                    out.push_str(&format!(
                        "f {} {} {}\n",
                        tri.vertex3_idx as usize + vertex_count,
                        tri.vertex2_idx as usize + vertex_count,
                        tri.vertex1_idx as usize + vertex_count
                    ));
                }
            } else {
                for tri in &block.triangles {
                    out.push_str(&format!(
                        "f {} {} {}\n",
                        tri.vertex1_idx as usize + vertex_count,
                        tri.vertex2_idx as usize + vertex_count,
                        tri.vertex3_idx as usize + vertex_count
                    ));
                }
            }

            vertex_count += block.vertices.len();
        }
    }

    Ok(out)
}

struct MmbModel {
    vertices: Vec<Vertex>,
    indices: Vec<u16>,
}

/// Zone VISUAL mesh (real walls/buildings/props geometry the client actually renders, not the
/// invisible collision/navmesh) as a Wavefront OBJ string -- adapted from xi-tinkerer's own
/// `processor::wavefront_obj::make_model_wavefront_file` (same repo, AGPLv3). Positions only, no
/// normals/UVs/materials -- Topaz's own MMB/MZB parsing doesn't carry per-triangle texture
/// assignment out to this layer, so this is real geometry without real texturing, same honest
/// scope tradeoff as the collision export. Same (x, -y, -z) convention as
/// parse_zone_collision_obj, so the same capture (x, -z) transform already verified there applies
/// here too.
#[pyfunction]
fn parse_zone_visual_obj(path: &str) -> PyResult<String> {
    let dat_path = PathBuf::from(path);
    let data = ZoneData::from_path(&dat_path)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Parse error: {e}")))?;

    let mmbs: HashMap<String, Vec<Vec<MmbModel>>> = data
        .chunks
        .iter()
        .filter_map(|chunk| match &chunk.data {
            ChunkData::ZoneMmb { zone_mmb } => Some(zone_mmb),
            _ => None,
        })
        .map(|mmb| {
            let blocks = mmb
                .blocks
                .iter()
                .map(|block| match &block.models {
                    ZoneMmbModels::Simple { models } => models
                        .iter()
                        .map(|model| MmbModel {
                            vertices: model
                                .vertices
                                .iter()
                                .map(|v| Vertex { x: v.x, y: v.y, z: v.z })
                                .collect(),
                            indices: model.indices.clone(),
                        })
                        .collect::<Vec<_>>(),
                    ZoneMmbModels::Complex { models } => models
                        .iter()
                        .map(|model| MmbModel {
                            vertices: model
                                .vertices
                                .iter()
                                .map(|v| Vertex { x: v.x, y: v.y, z: v.z })
                                .collect(),
                            indices: model.indices.clone(),
                        })
                        .collect::<Vec<_>>(),
                })
                .collect::<Vec<_>>();
            (mmb.header.mmb_id.clone(), blocks)
        })
        .collect();

    let mut out = String::new();
    let mut vertex_offset: usize = 1;
    for chunk in &data.chunks {
        let ChunkData::ZoneModel { zone_model } = &chunk.data else { continue };
        for (instance_idx, instance) in zone_model.model_block_instances.iter().enumerate() {
            let Some(blocks) = mmbs.get(&instance.id) else { continue };
            out.push_str(&format!("\no {}-{}\n", instance_idx, instance.id));

            let o2w = instance.to_world_matrix();
            let flip_vertices = o2w.determinant() <= 0f32;

            for block in blocks {
                for model in block {
                    for vertex in &model.vertices {
                        let vertex = o2w.apply_to_vertex(vertex);
                        out.push_str(&format!(
                            "v {} {} {}\n",
                            format_f32(vertex.x),
                            format_f32(-vertex.y),
                            format_f32(-vertex.z)
                        ));
                    }
                    for (i, indices) in model.indices.windows(3).enumerate() {
                        let (mut v1, v2, mut v3) = (
                            indices[0] as usize + vertex_offset,
                            indices[1] as usize + vertex_offset,
                            indices[2] as usize + vertex_offset,
                        );
                        let mut do_flip = flip_vertices;
                        if i % 2 == 0 {
                            do_flip = !do_flip;
                        }
                        if do_flip {
                            std::mem::swap(&mut v1, &mut v3);
                        }
                        out.push_str(&format!("f {v1} {v2} {v3}\n"));
                    }
                    vertex_offset += model.vertices.len();
                }
            }
        }
    }

    Ok(out)
}

#[pymodule]
fn xi_tinkerer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_menu_table, m)?)?;
    m.add_function(wrap_pyfunction!(parse_dialog, m)?)?;
    m.add_function(wrap_pyfunction!(parse_dmsg_table, m)?)?;
    m.add_function(wrap_pyfunction!(parse_entity_names, m)?)?;
    m.add_function(wrap_pyfunction!(parse_events, m)?)?;
    m.add_function(wrap_pyfunction!(parse_item_info, m)?)?;
    m.add_function(wrap_pyfunction!(parse_status_info, m)?)?;
    m.add_function(wrap_pyfunction!(parse_xistring_table, m)?)?;
    m.add_function(wrap_pyfunction!(parse_auto_translate, m)?)?;
    m.add_function(wrap_pyfunction!(parse_furniture_data, m)?)?;
    m.add_function(wrap_pyfunction!(parse_zone_collision_obj, m)?)?;
    m.add_function(wrap_pyfunction!(parse_zone_visual_obj, m)?)?;
    Ok(())
}
