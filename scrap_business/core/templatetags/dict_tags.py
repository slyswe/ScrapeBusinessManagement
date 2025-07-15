from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key)

@register.filter
def sum_weights(entries, scrap_type):
    # Use Python's built-in sum() function explicitly
    return sum(float(entry.weights.get(scrap_type, 0)) for entry in entries)

@register.filter
def sum_revenue(entries):
    return sum(entry.calculate_revenue() for entry in entries)

@register.filter
def add(value, arg):
    return float(value) + float(arg)

@register.filter
def sub(value, arg):
    return float(value) - float(arg)

@register.filter
def sum_field(items, field):
    """
    Sum a specific field from a list of items.
    items: Queryset or list of objects/dicts
    field: The field name to sum
    """
    return sum(float(getattr(item, field) if hasattr(item, field) else item[field]) for item in items)