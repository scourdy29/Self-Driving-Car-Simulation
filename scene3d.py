# scene3d.py


from panda3d.core import (
    GeomNode, Geom, GeomTriangles, GeomVertexData, GeomVertexFormat,
    GeomVertexWriter, NodePath, Vec4, Vec3, Point3,
    AmbientLight, DirectionalLight, PointLight,
    TextNode, CardMaker, LColor, TransparencyAttrib,
)

SCALE = 0.01   # Sim pixels

from config import PARKING_LOTS as _PARKING_LOTS

# Building heights
BUILDING_HEIGHTS = {
    "home":       0.8,
    "gas":        0.5,
    "school":     1.2,
    "restaurant": 0.6,
    "mall":       1.5,
    "airport":    1.0,
    "hospital":   1.8,
    "police":     0.9,
    "library":    1.0,
    "park":       0.3,
    "bank":       1.1,
    "fire":       0.9,
    "stadium":    2.0,
}


# Coordinate conversion
def s2p(sim_x: float, sim_y: float, z: float = 0.0) -> Point3:
    """Convert simulation (pixel) coords to Panda3D world coords."""
    return Point3(sim_x * SCALE, -sim_y * SCALE, z)


def sim_color_to_vec4(rgb_tuple, alpha=1.0) -> Vec4:
    r, g, b = rgb_tuple
    return Vec4(r / 255, g / 255, b / 255, alpha)


def make_box_node(cx, cy, cz, sx, sy, sz, color: Vec4) -> GeomNode:
    fmt  = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("box", fmt, Geom.UHStatic)
    vdata.setNumRows(24)

    vw  = GeomVertexWriter(vdata, "vertex")
    nw  = GeomVertexWriter(vdata, "normal")
    cw  = GeomVertexWriter(vdata, "color")

    faces = [
        (( 0,  0,  1), [(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]),   # top
        (( 0,  0, -1), [(-1,1,-1),(1,1,-1),(1,-1,-1),(-1,-1,-1)]),# bottom
        (( 1,  0,  0), [(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)]),    # right
        ((-1,  0,  0), [(-1,1,-1),(-1,-1,-1),(-1,-1,1),(-1,1,1)]),# left
        (( 0,  1,  0), [(1,1,-1),(-1,1,-1),(-1,1,1),(1,1,1)]),    # front
        (( 0, -1,  0), [(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)]),# back
    ]

    tris = GeomTriangles(Geom.UHStatic)
    vi   = 0
    for normal, corners in faces:
        for dx, dy, dz in corners:
            vw.addData3(cx + dx*sx, cy + dy*sy, cz + dz*sz)
            nw.addData3(*normal)
            cw.addData4(color)
        tris.addVertices(vi, vi+1, vi+2)
        tris.addVertices(vi, vi+2, vi+3)
        vi += 4

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("box")
    node.addGeom(geom)
    return node


def attach_box(parent: NodePath, cx, cy, cz, sx, sy, sz, color: Vec4) -> NodePath:
    node = make_box_node(cx, cy, cz, sx, sy, sz, color)
    np   = parent.attachNewNode(node)
    return np


# Ground plane
def build_ground(render: NodePath,
                 map_w: float, map_h: float) -> NodePath:
    cx = map_w * SCALE * 0.5
    cy = -map_h * SCALE * 0.5
    sx = map_w * SCALE * 0.5
    sy = map_h * SCALE * 0.5
    ground_color = Vec4(0.27, 0.51, 0.27, 1.0)
    return attach_box(render, cx, cy, -0.02, sx, sy, 0.01, ground_color)


# Roads
def build_roads(render: NodePath,
                road_x: list, road_y: list,
                half_w: float, map_w: float, map_h: float) -> NodePath:
    root       = render.attachNewNode("roads")
    road_color = Vec4(0.16, 0.16, 0.16, 1.0)
    line_color = Vec4(1.0, 0.63, 0.0,  1.0)   # amber dashes
    hw = half_w * SCALE

    # Vertical road strips
    for rx in road_x:
        cx = rx * SCALE
        cy = -map_h * SCALE * 0.5
        attach_box(root, cx, cy, 0.0, hw, map_h * SCALE * 0.5, 0.01, road_color)
        # dashed centre line
        y = 0
        while y < map_h:
            mid_y = -(y + 20) * SCALE
            attach_box(root, cx, mid_y, 0.015, 0.02, 20 * SCALE * 0.5, 0.005, line_color)
            y += 80

    # Horizontal road strips
    for ry in road_y:
        cx = map_w * SCALE * 0.5
        cy = -ry * SCALE
        attach_box(root, cx, cy, 0.0, map_w * SCALE * 0.5, hw, 0.01, road_color)
        # dashed centre line
        x = 0
        while x < map_w:
            mid_x = (x + 20) * SCALE
            attach_box(root, mid_x, cy, 0.015, 20 * SCALE * 0.5, 0.02, 0.005, line_color)
            x += 80

    return root


# Buildings

def build_parking_lots(render: NodePath) -> NodePath:
    """Draw a flat light-grey slab for every parking area."""
    root      = render.attachNewNode("parking_lots")
    lot_color = Vec4(0.62, 0.62, 0.62, 1.0)   # light grey tarmac
    line_color= Vec4(0.85, 0.85, 0.85, 1.0)   # white-ish lines

    for name, data in _PARKING_LOTS.items():
        sx, sy = data["spot"]
        cx = sx * SCALE
        cy = -sy * SCALE
        # Lot slab
        attach_box(root, cx, cy, 0.005, 0.20, 0.15, 0.005, lot_color)
        # Two parking space dividers
        for offset in [-0.07, 0.07]:
            attach_box(root, cx + offset, cy, 0.015, 0.01, 0.14, 0.005, line_color)
    return root


def build_buildings(render: NodePath, landmarks: list) -> NodePath:
    root = render.attachNewNode("buildings")

    for lm in landmarks:
        sx_sim, sy_sim = lm["size"]
        bx, by         = lm["pos"]
        btype          = lm["type"]
        height         = BUILDING_HEIGHTS.get(btype, 0.8)
        color          = sim_color_to_vec4(lm["color"])

        cx = bx * SCALE
        cy = -by * SCALE
        hx = sx_sim * SCALE * 0.5
        hy = sy_sim * SCALE * 0.5
        hz = height * 0.5

        # Main body
        attach_box(root, cx, cy, hz, hx, hy, hz, color)

        # Slightly darker roof detail
        roof_color = Vec4(color.x * 0.7, color.y * 0.7, color.z * 0.7, 1.0)
        attach_box(root, cx, cy, height + 0.05, hx * 0.9, hy * 0.9, 0.05, roof_color)

        # Name billboard
        tn = TextNode(f"label_{lm['name']}")
        tn.setText(lm["name"])
        tn.setAlign(TextNode.ACenter)
        tn.setTextColor(1, 1, 1, 1)
        tn.setCardColor(0, 0, 0, 0.6)
        tn.setCardAsMargin(0.1, 0.1, 0.05, 0.05)
        tn.setCardDecal(True)
        tnp = root.attachNewNode(tn)
        tnp.setScale(0.06)
        tnp.setPos(cx, cy, height + 0.25)
        tnp.setBillboardPointEye()   # always faces camera

    return root


# Traffic lights

def build_traffic_light_node(parent: NodePath) -> dict:
    root = parent.attachNewNode("light_fixture")

    pole_color  = Vec4(0.3, 0.3, 0.3, 1.0)
    box_color   = Vec4(0.15, 0.15, 0.15, 1.0)

    attach_box(root, 0, 0, 0.15, 0.03, 0.03, 0.15, pole_color)   # pole
    attach_box(root, 0, 0, 0.38, 0.07, 0.07, 0.08, box_color)    # housing

    lights_out = Vec4(0.2, 0.2, 0.2, 1.0)
    spheres = {}
    offsets = {"red": 0.46, "yellow": 0.38, "green": 0.30}
    colors  = {
        "red":    Vec4(0.9, 0.1, 0.1, 1.0),
        "yellow": Vec4(0.9, 0.8, 0.1, 1.0),
        "green":  Vec4(0.1, 0.9, 0.2, 1.0),
    }
    for name, z in offsets.items():
        on_np  = root.attachNewNode(make_box_node(0, 0, z, 0.04, 0.04, 0.04, colors[name]))
        off_np = root.attachNewNode(make_box_node(0, 0, z, 0.04, 0.04, 0.04, lights_out))
        spheres[name] = (on_np, off_np)

    return root, spheres


def build_all_traffic_lights(render: NodePath,
                             traffic_lights: list) -> dict:
    fixtures = {}
    for light in traffic_lights:
        root_np, spheres = build_traffic_light_node(render)
        root_np.setPos(s2p(light.x, light.y, 0))
        fixtures[light.id] = (root_np, spheres)
    return fixtures


def update_traffic_light_visuals(fixtures: dict, traffic_lights: list):
    from traffic import TrafficLightState
    for light in traffic_lights:
        if light.id not in fixtures:
            continue
        _, spheres = fixtures[light.id]
        active = (
            "red"    if light.state == TrafficLightState.RED    else
            "yellow" if light.state == TrafficLightState.YELLOW else
            "green"
        )
        for name, (on_np, off_np) in spheres.items():
            if name == active:
                on_np.show();  off_np.hide()
            else:
                on_np.hide();  off_np.show()


# Vehicles

def make_vehicle_node(parent: NodePath,
                      color_rgb: tuple,
                      is_player: bool = False) -> NodePath:
    root       = parent.attachNewNode("car")
    body_color = sim_color_to_vec4(color_rgb)
    roof_color = Vec4(body_color.x * 0.75, body_color.y * 0.75, body_color.z * 0.75, 1.0)
    wheel_col  = Vec4(0.08, 0.08, 0.08, 1.0)
    glass_col  = Vec4(0.55, 0.75, 1.0, 0.8)
    dark       = Vec4(body_color.x * 0.5, body_color.y * 0.5, body_color.z * 0.5, 1.0)

    # Body
    attach_box(root,  0,      0,     0.04,  0.045, 0.10,  0.04, body_color)
    # Cabin / roof
    attach_box(root,  0,     -0.01,  0.10,  0.035, 0.055, 0.03, roof_color)
    # Windshield
    attach_box(root,  0,      0.055, 0.09,  0.030, 0.005, 0.025, glass_col)
    # Rear detail strip
    attach_box(root,  0,     -0.09,  0.05,  0.038, 0.008, 0.015, dark)
    # Wheels
    for vx, vy in [(-0.055, 0.065), (0.055, 0.065),
                   (-0.055,-0.065), (0.055,-0.065)]:
        attach_box(root, vx, vy, 0.015, 0.015, 0.022, 0.015, wheel_col)

    # Player car
    if is_player:
        attach_box(root, 0, -0.01, 0.135, 0.030, 0.045, 0.005, Vec4(0.2, 0.5, 1.0, 1.0))

    return root


def create_vehicle_nodes(render: NodePath, vehicles: list) -> dict:
    nodes = {}
    for v in vehicles:
        from traffic import AgentType
        is_player = v.agent_type == AgentType.HUMAN
        nodes[v.id] = make_vehicle_node(render, v.color, is_player)
    return nodes


def sync_vehicle_nodes(nodes: dict, vehicles: list):
    for v in vehicles:
        if v.id not in nodes:
            continue
        np = nodes[v.id]
        np.setPos(s2p(v.x, v.y, 0.0))
        np.setH(-(v.angle + 90))


# Scene setup

def setup_lighting(render: NodePath):
    """Ambient + one directional sun light for simple shadows."""
    ambient      = AmbientLight("ambient")
    ambient.setColor(Vec4(0.45, 0.45, 0.45, 1))
    render.setLight(render.attachNewNode(ambient))

    sun          = DirectionalLight("sun")
    sun.setColor(Vec4(0.9, 0.85, 0.75, 1))
    sun_np       = render.attachNewNode(sun)
    sun_np.setHpr(45, -60, 0)
    render.setLight(sun_np)
