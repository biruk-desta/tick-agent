#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* The graph is the Python map's immutable 2 m grid. Keep the serial heap
 * duplicates and strict comparisons: both affect the 22,000-pop result. */
enum { ROUTE_LIMIT = 22000, ROUTE_SLICE = 512 };

typedef struct {
    float key, heuristic;
    int cell;
} Node;

typedef struct {
    int size, best, pops, done, goal, gx, gy;
    float best_h;
    Node *heap;
    float *cost;
    int *parent;
    unsigned char *closed;
} Route;

static void free_route(PyObject *capsule) {
    Route *route = PyCapsule_GetPointer(capsule, "practice.route");
    free(route->heap);
    free(route->cost);
    free(route->parent);
    free(route->closed);
    free(route);
}

static PyObject *start_route(PyObject *self, PyObject *args) {
    int start, goal, width, cells;
    double heuristic;
    if (!PyArg_ParseTuple(args, "iiiid", &start, &goal, &width, &cells, &heuristic))
        return NULL;
    Route *route = calloc(1, sizeof(*route));
    if (route == NULL)
        return PyErr_NoMemory();
    PyObject *capsule = PyCapsule_New(route, "practice.route", free_route);
    if (capsule == NULL) {
        free(route);
        return NULL;
    }
    route->heap = malloc((8 * ROUTE_LIMIT + 1) * sizeof(Node));
    route->cost = malloc(cells * sizeof(float));
    route->parent = malloc(cells * sizeof(int));
    route->closed = calloc(cells, sizeof(unsigned char));
    if (!route->heap || !route->cost || !route->parent || !route->closed) {
        Py_DECREF(capsule);
        return PyErr_NoMemory();
    }
    for (int i = 0; i < cells; i++)
        route->cost[i] = INFINITY;
    route->best = start;
    route->best_h = heuristic;
    route->goal = goal;
    route->gx = goal % width;
    route->gy = goal / width;
    route->heap[0] = (Node){heuristic, heuristic, start};
    route->size = 1;
    route->cost[start] = 0;
    route->parent[start] = -1;
    return capsule;
}

static Node pop_node(Route *route) {
    Node *heap = route->heap;
    Node first = heap[0], last = heap[--route->size];
    int index = 0;
    for (int child = 1; child < route->size; child = 2 * index + 1) {
        if (child + 1 < route->size && heap[child + 1].key < heap[child].key)
            child++;
        if (last.key <= heap[child].key)
            break;
        heap[index] = heap[child];
        index = child;
    }
    heap[index] = last;
    return first;
}

static void push_node(Route *route, Node node) {
    Node *heap = route->heap;
    int index = route->size++;
    while (index) {
        int parent = (index - 1) / 2;
        if (node.key >= heap[parent].key)
            break;
        heap[index] = heap[parent];
        index = parent;
    }
    heap[index] = node;
}

/* Map buffers stay alive with the capsule. The ray stamps are scratch
 * space accessed under the GIL. */
enum { STEPS, CLEARANCE, HEURISTICS, COSTS, HEIGHTS, BLOCKS, PRISMS,
       EDGES, EDGE_STARTS, BUCKET_STARTS, BUCKET_PRISMS, LANDINGS, LANDING_DISTANCES, MAP_BUFFERS };

typedef struct {
    Py_buffer buffers[MAP_BUFFERS];
    uint32_t *seen, stamp;
    int width, nx, ny, block_width, bucket_width, bucket_height;
    int offsets[8], prism_count;
    double x0, y0, bx, by, terrain_top, terrain_bottom, solid_top;
} Arena;

static void free_arena(Arena *map) {
    for (int i = 0; i < MAP_BUFFERS; i++)
        if (map->buffers[i].obj)
            PyBuffer_Release(&map->buffers[i]);
    free(map->seen);
    free(map);
}

static void free_arena_capsule(PyObject *capsule) {
    free_arena(PyCapsule_GetPointer(capsule, "practice.arena"));
}

static PyObject *load_arena(PyObject *self, PyObject *args) {
    Arena *map = calloc(1, sizeof(*map));
    PyObject *buffers;
    if (map == NULL)
        return PyErr_NoMemory();
    if (!PyArg_ParseTuple(args, "O(iiiiii)(ddddddd)", &buffers, &map->width,
                          &map->nx, &map->ny, &map->block_width, &map->bucket_width,
                          &map->bucket_height, &map->x0, &map->y0, &map->bx, &map->by,
                          &map->terrain_top, &map->terrain_bottom, &map->solid_top)) {
        free(map);
        return NULL;
    }
    if (!PyTuple_Check(buffers) || PyTuple_Size(buffers) != MAP_BUFFERS) {
        free(map);
        PyErr_SetString(PyExc_ValueError, "Missing practice map buffers");
        return NULL;
    }
    for (int i = 0; i < MAP_BUFFERS; i++) {
        if (PyObject_GetBuffer(PyTuple_GET_ITEM(buffers, i), &map->buffers[i], PyBUF_SIMPLE) < 0) {
            free_arena(map);
            return NULL;
        }
    }
    map->prism_count = map->buffers[PRISMS].len / (6 * sizeof(double));
    if (map->prism_count) {
        map->seen = calloc(map->prism_count, sizeof(uint32_t));
        if (map->seen == NULL) {
            free_arena(map);
            return PyErr_NoMemory();
        }
    }
    const int w = map->width;
    const int offsets[] = {1, -1, w, -w, w + 1, 1 - w, w - 1, -w - 1};
    memcpy(map->offsets, offsets, sizeof(offsets));
    PyObject *capsule = PyCapsule_New(map, "practice.arena", free_arena_capsule);
    if (capsule == NULL)
        free_arena(map);
    return capsule;
}

static PyObject *advance_route(PyObject *self, PyObject *args) {
    PyObject *arena_capsule, *route_capsule;
    if (!PyArg_ParseTuple(args, "OO", &arena_capsule, &route_capsule))
        return NULL;
    Arena *map = PyCapsule_GetPointer(arena_capsule, "practice.arena");
    Route *route = PyCapsule_GetPointer(route_capsule, "practice.route");
    if (!map || !route)
        return NULL;
    const unsigned char *steps = map->buffers[STEPS].buf;
    const unsigned char *clearance = map->buffers[CLEARANCE].buf;
    const float *heuristics = map->buffers[HEURISTICS].buf;
    const float *edge_cost = map->buffers[COSTS].buf;
    const int w = map->width;
    int end = route->pops + ROUTE_SLICE;
    if (end > ROUTE_LIMIT)
        end = ROUTE_LIMIT;
    while (!route->done && route->size && route->pops < end) {
        const Node node = pop_node(route);
        route->pops++;
        const int cell = node.cell;
        if (route->closed[cell])
            continue;
        if (cell == route->goal) {
            route->best = cell;
            route->done = 1;
            break;
        }
        route->closed[cell] = 1;
        if (node.heuristic < route->best_h) {
            route->best = cell;
            route->best_h = node.heuristic;
        }
        const float base = route->cost[cell];
        for (unsigned int mask = steps[cell]; mask; mask &= mask - 1) {
            const unsigned int i = __builtin_ctz(mask);
            const int next = cell + map->offsets[i];
            if (route->closed[next])
                continue;
            const float cost = base + edge_cost[(i >= 4) * 21 + clearance[next]];
            if (cost >= route->cost[next])
                continue;
            route->cost[next] = cost;
            route->parent[next] = cell;
            const float heur = heuristics[abs(next / w - route->gy) * w + abs(next % w - route->gx)];
            const Node queued = {cost + heur, heur, next};
            push_node(route, queued);
        }
    }
    route->done |= !route->size || route->pops == ROUTE_LIMIT;
    if (!route->done)
        Py_RETURN_NONE;
    int length = 0;
    for (int i = route->best; i != -1; i = route->parent[i])
        length++;
    PyObject *path = PyList_New(length);
    if (path == NULL)
        return NULL;
    for (int i = route->best; i != -1; i = route->parent[i]) {
        PyObject *cell = PyLong_FromLong(i);
        if (cell == NULL) {
            Py_DECREF(path);
            return NULL;
        }
        PyList_SET_ITEM(path, --length, cell);
    }
    return path;
}

static PyObject *escape_cell(PyObject *self, PyObject *args) {
    PyObject *capsule;
    int start;
    if (!PyArg_ParseTuple(args, "Oi", &capsule, &start))
        return NULL;
    Arena *map = PyCapsule_GetPointer(capsule, "practice.arena");
    if (!map)
        return NULL;
    const unsigned char *steps = map->buffers[STEPS].buf;
    const int *landings = map->buffers[LANDINGS].buf;
    const double *spans = map->buffers[LANDING_DISTANCES].buf;
    const int cells = map->buffers[STEPS].len, w = map->width;
    unsigned char *seen = calloc(cells, sizeof(unsigned char));
    int *queue = malloc(cells * sizeof(int));
    if (!seen || !queue) {
        free(queue);
        free(seen);
        return PyErr_NoMemory();
    }
    seen[start] = 1;
    queue[0] = start;
    double best_score = INFINITY;
    int best = -1, layer = 1, end = 1, n = 0;
    for (int head = 0; head < end && head < 60000; head++) {
        if (head == layer) {
            layer = end;
            n++;
        }
        if (2 * n >= best_score)
            break;
        const int cell = queue[head], land = landings[cell];
        if (land >= 0) {
            /* Landing prep grows at most 20 steps in either axis. */
            const double span = spans[abs(cell / w - land / w) * 21 + abs(cell % w - land % w)];
            const double score = 2 * n + 4 * span;
            if (score < best_score) {
                best = cell;
                best_score = score;
            }
        }
        for (unsigned int mask = steps[cell]; mask; mask &= mask - 1) {
            const int next = cell + map->offsets[__builtin_ctz(mask)];
            if (!seen[next]) {
                seen[next] = 1;
                queue[end++] = next;
            }
        }
    }
    free(queue);
    free(seen);
    return PyLong_FromLong(best);
}

static double clamp(double value, double high) {
    return value < 0 ? 0 : value > high ? high : value;
}

static double ground(const Arena *map, double x, double y) {
    if (map->terrain_top == map->terrain_bottom)
        return map->terrain_top;
    const double u = clamp(x - map->x0, map->nx - 1.000001);
    const double v = clamp(y - map->y0, map->ny - 1.000001);
    const int i = (int)u, j = (int)v;
    const double fx = u - i, fy = v - j;
    const float *g = (const float *)map->buffers[HEIGHTS].buf + j * map->nx + i;
    const double a = (1 - fx) * g[0] + fx * g[1];
    const double b = (1 - fx) * g[map->nx] + fx * g[map->nx + 1];
    return (1 - fy) * a + fy * b;
}

static int contains(const double *p, const double *edges, int begin, int end, double x, double y) {
    if (x < p[2] || y < p[3] || x > p[4] || y > p[5])
        return 0;
    int inside = 0;
    for (int i = begin; i < end; i++, edges += 4)
        if ((edges[1] > y) != (edges[1] + edges[3] > y) &&
            x < edges[0] + (y - edges[1]) * edges[2] / edges[3])
            inside = !inside;
    return inside;
}

static int solid(const Arena *map, double x, double y, double z) {
    if (z < ground(map, x, y))
        return 1;
    if (z >= map->solid_top)
        return 0;
    const int i = (int)floor((x - map->bx) / 16), j = (int)floor((y - map->by) / 16);
    if (i < 0 || i >= map->bucket_width || j < 0 || j >= map->bucket_height)
        return 0;
    const int cell = j * map->bucket_width + i;
    const int *starts = map->buffers[BUCKET_STARTS].buf;
    const int *prisms = map->buffers[BUCKET_PRISMS].buf;
    const int *edge_starts = map->buffers[EDGE_STARTS].buf;
    for (int k = starts[cell]; k < starts[cell + 1]; k++) {
        const int prism = prisms[k], begin = edge_starts[prism];
        const double *p = (const double *)map->buffers[PRISMS].buf + 6 * prism;
        const double *edges = (const double *)map->buffers[EDGES].buf + 4 * begin;
        if (p[0] < z && z < p[1] && contains(p, edges, begin, edge_starts[prism + 1], x, y))
            return 1;
    }
    return 0;
}

static PyObject *shell_impact(PyObject *self, PyObject *args) {
    PyObject *capsule;
    double x, y, z, vx, vy, vz, gravity;
    if (!PyArg_ParseTuple(args, "O(ddd)(ddd)d", &capsule, &x, &y, &z, &vx, &vy, &vz, &gravity))
        return NULL;
    Arena *map = PyCapsule_GetPointer(capsule, "practice.arena");
    if (!map)
        return NULL;
    const double dx = vx * 0.05, dy = vy * 0.05;
    for (double clock = 0; clock < 2.5; clock += 0.05) {
        x += dx;
        y += dy;
        z += vz * 0.05;
        vz -= gravity * 0.05;
        if (solid(map, x, y, z))
            return Py_BuildValue("(dd)", x, y);
    }
    Py_RETURN_NONE;
}

static int prism_blocks(const Arena *map, int prism, const double *start, const double *delta,
                        const double *low, const double *high) {
    const double *p = (const double *)map->buffers[PRISMS].buf + 6 * prism;
    const double lower[] = {p[2], p[3], p[0]}, upper[] = {p[4], p[5], p[1]};
    double enter = 0, leave = 1;
    for (int axis = 0; axis < 3; axis++) {
        if (low[axis] > upper[axis] || high[axis] < lower[axis])
            return 0;
        const double o = start[axis], d = delta[axis];
        if (fabs(d) < 1e-9) {
            if (o < lower[axis] || o > upper[axis])
                return 0;
            continue;
        }
        const double a = (lower[axis] - o) / d, b = (upper[axis] - o) / d;
        enter = fmax(enter, fmin(a, b));
        leave = fmin(leave, fmax(a, b));
        if (enter > leave)
            return 0;
    }
    const int *starts = map->buffers[EDGE_STARTS].buf;
    const int begin = starts[prism], end = starts[prism + 1];
    const double *edges = (const double *)map->buffers[EDGES].buf + 4 * begin;
    const double x = start[0], y = start[1], z = start[2];
    const double dx = delta[0], dy = delta[1], dz = delta[2];
    if (p[0] <= z && z <= p[1] && contains(p, edges, begin, end, x, y))
        return 1;
    if (fabs(dz) > 1e-9) {
        const double t = ((dz > 0 ? p[0] : p[1]) - z) / dz;
        if (0 <= t && t < 1 && contains(p, edges, begin, end, x + dx * t, y + dy * t))
            return 1;
    }
    for (int i = begin; i < end; i++, edges += 4) {
        const double cross = dx * edges[3] - dy * edges[2];
        if (fabs(cross) < 1e-9)
            continue;
        const double px = edges[0] - x, py = edges[1] - y;
        const double t = (px * edges[3] - py * edges[2]) / cross;
        if (0 <= t && t < 1 && p[0] <= z + dz * t && z + dz * t <= p[1]) {
            const double side = (px * dy - py * dx) / cross;
            if (0 <= side && side <= 1)
                return 1;
        }
    }
    return 0;
}

static int prism_clear(Arena *map, const double *start, const double *end, const double *delta) {
    const int *starts = map->buffers[BUCKET_STARTS].buf;
    const int *prisms = map->buffers[BUCKET_PRISMS].buf;
    const double x = start[0], y = start[1], dx = delta[0], dy = delta[1];
    const double bx = map->bx, by = map->by;
    int i = (int)floor((x - bx) / 16), j = (int)floor((y - by) / 16);
    const int ei = (int)floor((end[0] - bx) / 16), ej = (int)floor((end[1] - by) / 16);
    const int si = fabs(dx) > 1e-9 ? (dx > 0 ? 1 : -1) : 0;
    const int sj = fabs(dy) > 1e-9 ? (dy > 0 ? 1 : -1) : 0;
    double tx = si ? (bx + (i + (si > 0)) * 16 - x) / dx : INFINITY;
    double ty = sj ? (by + (j + (sj > 0)) * 16 - y) / dy : INFINITY;
    const double dtx = si ? fabs(16 / dx) : INFINITY, dty = sj ? fabs(16 / dy) : INFINITY;
    const double low[] = {fmin(x, end[0]), fmin(y, end[1]), fmin(start[2], end[2])};
    const double high[] = {fmax(x, end[0]), fmax(y, end[1]), fmax(start[2], end[2])};
    if (++map->stamp == 0) {
        memset(map->seen, 0, map->prism_count * sizeof(uint32_t));
        map->stamp = 1;
    }
    for (int n = 0; n < 4096; n++) {
        if (0 <= i && i < map->bucket_width && 0 <= j && j < map->bucket_height) {
            const int cell = j * map->bucket_width + i;
            for (int k = starts[cell]; k < starts[cell + 1]; k++) {
                const int prism = prisms[k];
                if (map->seen[prism] != map->stamp) {
                    if (prism_blocks(map, prism, start, delta, low, high))
                        return 0;
                    map->seen[prism] = map->stamp;
                }
            }
        }
        if ((i == ei || !si) && (j == ej || !sj))
            break;
        if (si && i != ei && (tx < ty || j == ej || !sj)) {
            i += si;
            tx += dtx;
        } else {
            j += sj;
            ty += dty;
        }
    }
    return 1;
}

static int terrain_clear(const Arena *map, const double *start, const double *end, const double *delta,
                         double step) {
    const double x = start[0], y = start[1], z = start[2];
    const double dx = delta[0], dy = delta[1], dz = delta[2];
    const double *blocks = map->buffers[BLOCKS].buf;
    double t = 0;
    for (int n = 0; n < 100001; n++) {
        const double u = x + dx * t - map->x0, v = y + dy * t - map->y0;
        if (0 <= u && u < map->nx && 0 <= v && v < map->ny) {
            const int i = (int)u / 8, j = (int)v / 8;
            const double peak = blocks[j * map->block_width + i];
            if (z + dz * t > peak) {
                const double tx = dx ? (8 * (i + (dx > 0)) + map->x0 - x) / dx : INFINITY;
                const double ty = dy ? (8 * (j + (dy > 0)) + map->y0 - y) / dy : INFINITY;
                const double edge = fmin(1, fmin(tx, ty) + 1e-6);
                if (edge > t && z + dz * edge > peak) {
                    t = edge;
                    if (t >= 1)
                        return 1;
                    continue;
                }
            }
        }
        t += step;
        if (t >= 1)
            return end[2] >= ground(map, end[0], end[1]);
        if (z + dz * t < ground(map, x + dx * t, y + dy * t))
            return 0;
    }
    return 1;
}

static PyObject *clear_ray(PyObject *self, PyObject *args) {
    PyObject *capsule;
    double start[3], end[3], step;
    if (!PyArg_ParseTuple(args, "O(ddd)(ddd)d", &capsule, &start[0], &start[1], &start[2],
                          &end[0], &end[1], &end[2], &step))
        return NULL;
    for (int i = 0; i < 3; i++)
        if (!(start[i] > -1e8 && start[i] < 1e8 && end[i] > -1e8 && end[i] < 1e8))
            Py_RETURN_NONE;
    Arena *map = PyCapsule_GetPointer(capsule, "practice.arena");
    if (!map)
        return NULL;
    const double low = fmin(start[2], end[2]);
    const int check_terrain = low <= map->terrain_top;
    if (check_terrain && start[2] < ground(map, start[0], start[1]))
        Py_RETURN_FALSE;
    const double delta[] = {end[0] - start[0], end[1] - start[1], end[2] - start[2]};
    if (map->prism_count && low <= map->solid_top && !prism_clear(map, start, end, delta))
        Py_RETURN_FALSE;
    if (!check_terrain)
        Py_RETURN_TRUE;
    if (!step || map->terrain_top == map->terrain_bottom)
        return PyBool_FromLong(end[2] >= ground(map, end[0], end[1]));
    return PyBool_FromLong(terrain_clear(map, start, end, delta, step));
}

static PyMethodDef methods[] = {
    {"load_arena", load_arena, METH_VARARGS, NULL},
    {"start_route", start_route, METH_VARARGS, NULL},
    {"advance_route", advance_route, METH_VARARGS, NULL},
    {"escape_cell", escape_cell, METH_VARARGS, NULL},
    {"clear_ray", clear_ray, METH_VARARGS, NULL},
    {"shell_impact", shell_impact, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_practice_fast", NULL, -1, methods
};

PyMODINIT_FUNC PyInit__practice_fast(void) {
    return PyModule_Create(&module);
}
