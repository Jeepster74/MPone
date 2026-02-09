import json
import os

def simplify_geojson(input_path, output_path, precision=4):
    print(f"Simplifying {input_path}...")
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    with open(input_path, 'r') as f:
        data = json.load(f)

    original_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"Original size: {original_size:.2f} MB")

    new_features = []
    for feature in data.get('features', []):
        # 1. Simplify geometry coordinates
        geom = feature.get('geometry', {})
        if geom and geom.get('type') in ['Polygon', 'MultiPolygon']:
            def thin_coords(rings):
                thinned = []
                for ring in rings:
                    # Keep at most 150 points for dashboard visualization
                    step = max(1, len(ring) // 150)
                    new_ring = ring[::step]
                    # Ensure first/last point match if it's a closed ring
                    if len(new_ring) > 0 and new_ring[0] != new_ring[-1]:
                        new_ring.append(new_ring[0])
                    # Round coordinates
                    new_ring = [[round(coord, precision) for coord in pt] for pt in new_ring]
                    thinned.append(new_ring)
                return thinned

            if geom['type'] == 'Polygon':
                geom['coordinates'] = thin_coords(geom.get('coordinates', []))
            elif geom['type'] == 'MultiPolygon':
                new_multi = []
                for poly in geom.get('coordinates', []):
                    new_multi.append(thin_coords(poly))
                geom['coordinates'] = new_multi
        
        # 2. Strip unnecessary properties
        props = feature.get('properties', {})
        essential_props = {'track_id'}
        feature['properties'] = {k: v for k, v in props.items() if k in essential_props}
        
        new_features.append(feature)

    data['features'] = new_features

    with open(output_path, 'w') as f:
        json.dump(data, f, separators=(',', ':')) # Compact JSON

    new_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"New size: {new_size:.2f} MB")
    print(f"Reduction: {((original_size - new_size) / original_size) * 100:.1f}%")

if __name__ == "__main__":
    base_path = "/Users/jaap.vanoort/Documents/MP One/Market Analysis/data"
    simplify_geojson(
        os.path.join(base_path, "karting_shapes.geojson"),
        os.path.join(base_path, "karting_shapes_simple.geojson"),
        precision=5
    )
    # Also overwrite the one in premium-dashboard/data
    simplify_geojson(
        os.path.join(base_path, "karting_shapes.geojson"),
        "/Users/jaap.vanoort/Documents/MP One/Market Analysis/premium-dashboard/data/karting_shapes.geojson",
        precision=5
    )
