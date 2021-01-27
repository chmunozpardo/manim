import itertools as it
import re
import string
import warnings

from xml.dom import minidom

from manimlib.utils.arcs_bezier import arc_to_bezier
from manimlib.constants import *
from manimlib.mobject.geometry import Circle
from manimlib.mobject.geometry import Rectangle
from manimlib.mobject.geometry import RoundedRectangle
from manimlib.mobject.types.vectorized_mobject import VGroup
from manimlib.mobject.types.vectorized_mobject import VMobject
from manimlib.utils.color import *
from manimlib.utils.config_ops import digest_config
from manimlib.utils.config_ops import digest_locals


def string_to_numbers(num_string, arc=False):
    output = []
    num_string = num_string.replace("-", ",-")
    num_string = num_string.replace("e,-", "e-")
    if arc:
        num_string = re.sub("(\d*\.?\d+)\s?(\d*\.?\d+)\s?([0-1])\s?([0-1])\s?([0-1])\s?", r"\1 \2 \3 \4 \5 ", num_string)
    for s in re.split("[ ,]", num_string):
        if len(re.split("[ .]", s)) > 2:
            tmp = re.split("[ .]", s)
            first = tmp[0]+"."+tmp[1]
            output.append(float(first))
            for t in tmp[2:]:
                output.append(float("."+t))
        elif s != "":
            output.append(float(s))
    return output

class SVGMobject(VMobject):
    CONFIG = {
        "should_center": True,
        "height": 5,
        "width": None,
        # Must be filled in in a subclass, or when called
        "file_name": None,
        "fill_colors": True,
        "unpack_groups": True,  # if False, creates a hierarchy of VGroups
        "stroke_width": 0.0,
        "fill_opacity": 1.0,
        # "fill_color" : LIGHT_GREY,
    }

    def __init__(self, file_name=None, **kwargs):
        digest_config(self, kwargs)
        self.file_name = file_name or self.file_name
        self.color_fills = []
        self.ensure_valid_file()
        # self.height = 0
        # self.width = 0
        VMobject.__init__(self, **kwargs)
        self.move_into_position()

    def check_stroke_width(self, element):
        if not isinstance(element, minidom.Element):
            return "none"
        else:
            fill_t = element.getAttribute('stroke-width')
            fill_style = element.getAttribute('style')
            if fill_t and not fill_t == "none":
                return fill_t
            elif fill_style and not fill_style == "none":
                if re.search("stroke-width:(-?[0-9]*(\.[0-9]*)?){1}", fill_style):
                    splt = re.split("stroke-width:(-?[0-9]*(\.[0-9]*)?){1}", fill_style)[1]
                    return float(splt)
                else:
                    return self.check_stroke_width(element.parentNode)
            else:
                return self.check_stroke_width(element.parentNode)

    def check_stroke_color(self, element):
        if not isinstance(element, minidom.Element):
            return "none"
        else:
            fill_t = element.getAttribute('stroke')
            fill_style = element.getAttribute('style')
            if fill_t and not fill_t == "none":
                if len(fill_t) == 4:
                    fill_t = "#" + fill_t[1]*2 + fill_t[2]*2 + fill_t[3]*2
                return fill_t
            elif fill_style and not fill_style == "none":
                if re.search("stroke:(#[0-9a-fA-F]+){1}", fill_style):
                    splt = re.split("stroke:(#[0-9a-fA-F]+){1}", fill_style)[1]
                    if len(splt) == 4:
                        splt = "#" + splt[1]*2 + splt[2]*2 + splt[3]*2
                    return splt
                else:
                    return self.check_stroke_color(element.parentNode)
            else:
                return self.check_stroke_color(element.parentNode)

    def check_fill(self, element):
        if not isinstance(element, minidom.Element):
            return "none"
        else:
            fill_t = element.getAttribute('fill')
            fill_style = element.getAttribute('style')
            if fill_t and not fill_t == "none":
                if fill_t[:3] == "url":
                    return "none"
                if len(fill_t) == 4:
                    fill_t = "#" + fill_t[1]*2 + fill_t[2]*2 + fill_t[3]*2
                return fill_t
            elif fill_style and not fill_style == "none":
                if re.search("fill:(#[0-9a-fA-F]+){1}", fill_style):
                    splt = re.split("fill:(#[0-9a-fA-F]+){1}", fill_style)[1]
                    if fill_t[:3] == "url":
                        return "none"
                    if len(splt) == 4:
                        splt = "#" + splt[1]*2 + splt[2]*2 + splt[3]*2
                    return splt
                else:
                    return self.check_fill(element.parentNode)
            else:
                return self.check_fill(element.parentNode)

    # Colors
    def init_colors(self):
        if len(self.submobjects) > 0:
            for m in self.submobjects:
                m.init_colors()
        self.fill_opacity = 1.0
        self.fill_rgbas = np.array([[1.0, 1.0, 1.0, 1.0]])
        self.background_stroke_rgbas = np.array([[0.0, 0.0, 0.0, 1.0]])
        self.stroke_rgbas = np.array([[0.0, 0.0, 0.0, 1.0]])
        self.stroke_width = 1.0
        self.stroke_opacity = 1.0
        
        return self

    def ensure_valid_file(self):
        if self.file_name is None:
            raise Exception("Must specify file for SVGMobject")
        possible_paths = [
            os.path.join(os.path.join("assets", "svg_images"), self.file_name),
            os.path.join(os.path.join("assets", "svg_images"), self.file_name + ".svg"),
            os.path.join(os.path.join("assets", "svg_images"), self.file_name + ".xdv"),
            self.file_name,
        ]
        for path in possible_paths:
            if os.path.exists(path):
                self.file_path = path
                return
        raise IOError("No file matching %s in image directory" %
                      self.file_name)

    def generate_points(self):
        doc = minidom.parse(self.file_path)
        self.ref_to_element = {}
        for svg in doc.getElementsByTagName("svg"):
            mobjects = self.get_mobjects_from(svg)
            if self.unpack_groups:
                self.add(*mobjects)
            else:
                self.add(*mobjects[0].submobjects)
        doc.unlink()

    def get_mobjects_from(self, element):
        result = []
        if not isinstance(element, minidom.Element):
            return result
        if element.getAttribute('id'):
            self.update_ref_to_element(element)
        if element.tagName == 'defs':
            self.update_ref_to_element(element)
        elif element.tagName == 'style':
            pass  # TODO, handle style
        elif element.tagName in ['g', 'svg', 'symbol']:
            result += it.chain(*[
                self.get_mobjects_from(child)
                for child in element.childNodes
            ])
        elif element.tagName == 'path':
            temp = element.getAttribute('d')
            if temp != '':
                result.append(self.path_string_to_mobject(temp))
        elif element.tagName == 'use':
            result += self.use_to_mobjects(element)
        elif element.tagName == 'rect':
            result.append(self.rect_to_mobject(element))
        elif element.tagName == 'circle':
            result.append(self.circle_to_mobject(element))
        elif element.tagName == 'ellipse':
            result.append(self.ellipse_to_mobject(element))
        elif element.tagName in ['polygon', 'polyline']:
            result.append(self.polygon_to_mobject(element))
        else:
            pass  # TODO
    
        # We check for color fill and strokes
        if len(result) > 0:
            if element.tagName not in ['id', 'g', 'svg', 'symbol', 'style', 'use']:
                fill_color = self.check_fill(element)
                strike_width = self.check_stroke_width(element)
                strike_color = self.check_stroke_color(element)
                deleted = False
                if not fill_color == "none":
                    result[-1].set_fill(fill_color, opacity=1.0)
                    if not strike_width == "none":
                        strike_width = float(strike_width)
                        if not strike_color == "none":
                            result[-1].set_stroke(color=strike_color, width=strike_width, opacity=1.0)
                        else:
                            result[-1].set_stroke(color=BLACK, width=strike_width, opacity=1.0)
                    elif not strike_color == "none":
                        strike_width = 1.0
                        result[-1].set_stroke(color=strike_color, width=strike_width, opacity=1.0)
                # If the last element was not a TeX string and has no color
                # we delete it
                elif not hasattr(self, "tex_string"):
                    del result[-1]
            # warnings.warn("Unknown element type: " + element.tagName)
        result = [m for m in result if m is not None]
        self.handle_transforms(element, VGroup(*result))
        if len(result) > 1 and not self.unpack_groups:
            result = [VGroup(*result)]
        return result

    def g_to_mobjects(self, g_element):
        mob = VGroup(*self.get_mobjects_from(g_element))
        self.handle_transforms(g_element, mob)
        return mob.submobjects

    def path_string_to_mobject(self, path_string):
        return VMobjectFromSVGPathstring(path_string)

    def use_to_mobjects(self, use_element):
        # Remove initial "#" character
        ref = use_element.getAttribute("xlink:href")[1:]
        if ref not in self.ref_to_element:
            warnings.warn("%s not recognized" % ref)
            return VGroup()
        return self.get_mobjects_from(
            self.ref_to_element[ref]
        )

    def attribute_to_float(self, attr):
        stripped_attr = "".join([
            char for char in attr
            if char in string.digits + "." + "-"
        ])
        return float(stripped_attr)

    def polygon_to_mobject(self, polygon_element):
        # TODO, This seems hacky...
        path_string = polygon_element.getAttribute("points")
        for digit in string.digits:
            path_string = path_string.replace(" " + digit, " L" + digit)
        path_string = "M" + path_string
        return self.path_string_to_mobject(path_string)

    def circle_to_mobject(self, circle_element):
        x, y, r = [
            self.attribute_to_float(
                circle_element.getAttribute(key)
            )
            if circle_element.hasAttribute(key)
            else 0.0
            for key in ("cx", "cy", "r")
        ]
        return Circle(radius=r).shift(x * RIGHT + y * DOWN)

    def ellipse_to_mobject(self, circle_element):
        x, y, rx, ry = [
            self.attribute_to_float(
                circle_element.getAttribute(key)
            )
            if circle_element.hasAttribute(key)
            else 0.0
            for key in ("cx", "cy", "rx", "ry")
        ]
        return Circle().scale(rx * RIGHT + ry * UP).shift(x * RIGHT + y * DOWN)

    def rect_to_mobject(self, rect_element):
        fill_color = rect_element.getAttribute("fill")
        stroke_color = rect_element.getAttribute("stroke")
        stroke_width = rect_element.getAttribute("stroke-width")
        corner_radius = rect_element.getAttribute("rx")
        opacity = 1
        # input preprocessing
        if fill_color in ["", "none", "#FFF", "#FFFFFF"] or Color(fill_color) == Color(WHITE):
            opacity = 0
            fill_color = BLACK  # shdn't be necessary but avoids error msgs
        if fill_color in ["#000", "#000000"]:
            fill_color = WHITE
        if stroke_color in ["", "none", "#FFF", "#FFFFFF"] or Color(stroke_color) == Color(WHITE):
            stroke_width = 0
            stroke_color = BLACK
        if stroke_color in ["#000", "#000000"]:
            stroke_color = WHITE
        if stroke_width in ["", "none", "0"]:
            stroke_width = 0

        if corner_radius in ["", "0", "none"]:
            corner_radius = 0

        corner_radius = float(corner_radius)

        if corner_radius == 0:
            mob = Rectangle(
                width=self.attribute_to_float(
                    rect_element.getAttribute("width")
                ),
                height=self.attribute_to_float(
                    rect_element.getAttribute("height")
                ),
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                fill_color=fill_color,
                fill_opacity=opacity
            )
        else:
            mob = RoundedRectangle(
                width=self.attribute_to_float(
                    rect_element.getAttribute("width")
                ),
                height=self.attribute_to_float(
                    rect_element.getAttribute("height")
                ),
                stroke_width=stroke_width,
                stroke_color=stroke_color,
                fill_color=fill_color,
                fill_opacity=opacity,
                corner_radius=corner_radius
            )

        mob.shift(mob.get_center() - mob.get_corner(UP + LEFT))
        return mob

    def handle_transforms(self, element, mobject):
        x, y = 0, 0
        try:
            x_attr = element.getAttribute('x')
            y_attr = element.getAttribute('y')
            if x_attr:
                x = self.attribute_to_float(x_attr)
            # Flip y
            else:
                x = 0
            if y_attr:
                y = -self.attribute_to_float(y_attr)
            else:
                y = 0
            mobject.shift(x * RIGHT + y * UP)
        except:
            pass

        transform = element.getAttribute('transform')

        try:  # transform matrix
            prefix = "matrix("
            suffix = ")"
            if not transform.startswith(prefix) or not transform.endswith(suffix):
                raise Exception()
            transform = transform[len(prefix):-len(suffix)]
            transform = string_to_numbers(transform)
            transform = np.array(transform).reshape([3, 2])
            x = transform[2][0]
            y = -transform[2][1]
            matrix = np.identity(self.dim)
            matrix[:2, :2] = transform[:2, :]
            matrix[1] *= -1
            matrix[:, 1] *= -1

            for mob in mobject.family_members_with_points():
                mob.points = np.dot(mob.points, matrix)
            mobject.shift(x * RIGHT + y * UP)
        except:
            pass

        try:  # transform scale
            prefix = "scale("
            suffix = ")"
            if not transform.startswith(prefix) or not transform.endswith(suffix):
                raise Exception()
            transform = transform[len(prefix):-len(suffix)]
            scale_values = string_to_numbers(transform)
            if len(scale_values) == 2:
                scale_x, scale_y = scale_values
                mobject.scale(np.array([scale_x, scale_y, 1]), about_point=ORIGIN)
            elif len(scale_values) == 1:
                scale = scale_values[0]
                mobject.scale(np.array([scale, scale, 1]), about_point=ORIGIN)
        except:
            pass

        try:  # transform translate
            prefix = "translate("
            suffix = ")"
            if not transform.startswith(prefix) or not transform.endswith(suffix):
                raise Exception()
            transform = transform[len(prefix):-len(suffix)]
            x, y = string_to_numbers(transform)
            mobject.shift(x * RIGHT + y * DOWN)
        except:
            pass
        # TODO, ...

    def flatten(self, input_list):
        output_list = []
        for i in input_list:
            if isinstance(i, list):
                output_list.extend(self.flatten(i))
            else:
                output_list.append(i)
        return output_list

    def get_all_childNodes_have_id(self, element):
        all_childNodes_have_id = []
        if not isinstance(element, minidom.Element):
            return
        if element.hasAttribute('id'):
            return [element]
        for e in element.childNodes:
            all_childNodes_have_id.append(self.get_all_childNodes_have_id(e))
        return self.flatten([e for e in all_childNodes_have_id if e])

    def update_ref_to_element(self, defs):
        new_refs = dict([(e.getAttribute('id'), e) for e in self.get_all_childNodes_have_id(defs)])
        self.ref_to_element.update(new_refs)

    def move_into_position(self):
        if self.should_center:
            self.center()
        if self.height is not None:
            self.set_height(self.height)
        if self.width is not None:
            self.set_width(self.width)


class VMobjectFromSVGPathstring(VMobject):
    def __init__(self, path_string, **kwargs):
        digest_locals(self)
        self.start_point = [0.0, 0.0, 0.0]
        self.z_state = False
        VMobject.__init__(self, **kwargs)

    def get_path_commands(self):
        result = [
            "M",  # moveto
            "L",  # lineto
            "H",  # horizontal lineto
            "V",  # vertical lineto
            "C",  # curveto
            "S",  # smooth curveto
            "Q",  # quadratic Bezier curve
            "T",  # smooth quadratic Bezier curveto
            "A",  # elliptical Arc
            "Z",  # closepath
        ]
        result += [s.lower() for s in result]
        return result

    def generate_points(self):
        pattern = "[%s]" % ("".join(self.get_path_commands()))
        pairs = list(zip(
            re.findall(pattern, self.path_string),
            re.split(pattern, self.path_string)[1:]
        ))
        # Which mobject should new points be added to
        self = self
        for command, coord_string in pairs:
            self.handle_command(command, coord_string)
        # people treat y-coordinate differently
        self.rotate(np.pi, RIGHT, about_point=ORIGIN)

    def handle_command(self, command, coord_string):
        isLower = command.islower()
        command = command.upper()
        # new_points are the points that will be added to the curr_points
        # list. This variable may get modified in the conditionals below.
        points = self.points
        arc_bool = command == "A"
        new_points = self.string_to_points(coord_string, arc=arc_bool)
        vh_points = string_to_numbers(coord_string, arc=arc_bool)

        temp_points = new_points.copy()
        if isLower and len(points) > 0:
            new_points += points[-1]

        if command == "M":  # moveto
            if len(points) == 0:
                self.start_point = new_points[0]
            if self.z_state:
                self.z_state = False
                if isLower:
                    new_points[0] = self.start_point + temp_points[0]
                    self.start_point = new_points[0]
            self.start_new_path(new_points[0])
            if len(new_points) <= 1:
                return

            # Draw relative line-to values.
            points = self.points
            new_points = temp_points[1:]
            command = "L"

            for p in new_points:
                if isLower:
                    # Treat everything as relative line-to until empty
                    p[0] += self.points[-1, 0]
                    p[1] += self.points[-1, 1]
                self.add_line_to(p)
            return

        elif command in ["L", "H", "V"]:  # lineto
            if command == "H":
                diff = np.array([0.0, 0.0, 0.0])
                for i in range(len(vh_points)):
                    if isLower:
                        diff[0] += vh_points[i]
                        self.add_line_to(points[-1] + diff)
                    else:
                        new_points[i, 1] = points[-1, 1]
                        self.add_line_to(new_points[i])
            elif command == "V":
                diff = np.array([0.0, 0.0, 0.0])
                for i in range(len(vh_points)):
                    if isLower:
                        diff[1] += vh_points[i]
                        self.add_line_to(points[-1] + diff)
                    else:
                        new_points[i, 1] = new_points[i, 0]
                        new_points[i, 0] = points[-1, 0]
                        self.add_line_to(new_points[i])
            elif command == "L":
                diff = 0
                for i in range(len(new_points)):
                    if isLower:
                        diff += temp_points[i]
                        self.add_line_to(points[-1] + diff)
                    else:
                        self.add_line_to(new_points[i])
            return

        if command == "C":  # curveto
            pass  # Yay! No action required
        elif command in ["S", "T"]:  # smooth curveto
            self.add_smooth_curve_to(*new_points[0:2])
            # handle1 = points[-1] + (points[-1] - points[-2])
            # new_points = np.append([handle1], new_points, axis=0)
            if len(new_points) > 2:
            # Add subsequent offset points relatively.
                for i in range(2, len(new_points), 2):
                    if isLower:
                        new_points[i:i + 2] -= points[-1]
                        new_points[i:i + 2] += new_points[i - 1]
                    self.add_smooth_curve_to(*new_points[i:i+2])
            return
        elif command == "Q":  # quadratic Bezier curve
            # TODO, this is a suboptimal approximation
            for i in range(0, len(new_points), 2):
                tmp = []
                if isLower:
                    tmp = [
                        2/3*temp_points[i],
                        2/3*temp_points[i] + 1/3*temp_points[i+1],
                        temp_points[i+1]
                    ] + self.points[-1]
                else:
                    tmp = [
                        1/3*self.points[-1] + 2/3*new_points[i],
                        1/3*new_points[i+1] + 2/3*new_points[i],
                        new_points[i+1]
                    ]
                self.add_cubic_bezier_curve_to(*tmp)
            return
        elif command == "A":  # elliptical Arc
            previous_point = self.points[-1]
            arc_parameters = string_to_numbers(coord_string, arc=True)
            if isLower:
                arc_parameters[5] = arc_parameters[5] + previous_point[0]
                arc_parameters[6] = arc_parameters[6] + previous_point[1]
            curves = arc_to_bezier(
                px = previous_point[0],
                py = previous_point[1],
                rx = arc_parameters[0],
                ry = arc_parameters[1],
                xAxisRotation = arc_parameters[2],
                largeArcFlag = arc_parameters[3],
                sweepFlag = arc_parameters[4],
                cx = arc_parameters[5],
                cy = arc_parameters[6]
            )
            for curve in curves:
                self.add_cubic_bezier_curve_to(*curve)
            return
        elif command == "Z":  # closepath
            self.z_state = True
            #self.add_line_to(self.start_point)
            return

        # Add first three points
        self.add_cubic_bezier_curve_to(*new_points[0:3])

        # Handle situations where there's multiple relative control points
        if len(new_points) > 3:
            # Add subsequent offset points relatively.
            for i in range(3, len(new_points), 3):
                if isLower:
                    new_points[i:i + 3] -= points[-1]
                    new_points[i:i + 3] += new_points[i - 1]
                self.add_cubic_bezier_curve_to(*new_points[i:i+3])

    def string_to_points(self, coord_string, arc=False):
        numbers = string_to_numbers(coord_string, arc)
        if len(numbers) % 2 == 1:
            numbers.append(0)
        num_points = len(numbers) // 2
        result = np.zeros((num_points, self.dim))
        result[:, :2] = np.array(numbers).reshape((num_points, 2))
        return result

    def get_original_path_string(self):
        return self.path_string
