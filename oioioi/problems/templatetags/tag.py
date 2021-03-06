from django.template import Library

from oioioi.base.utils.tags import get_tag_colors

register = Library()


@register.simple_tag
def tag_label(tag):
    colors = get_tag_colors(tag.name)
    return '<span title="%(name)s" class="label"' \
            ' style="background-color: %(bgcolor)s; color: %(textcolor)s;"' \
            '>%(name)s</span>' \
            % {'name': tag.name, 'bgcolor': colors[0], 'textcolor': colors[1]}
