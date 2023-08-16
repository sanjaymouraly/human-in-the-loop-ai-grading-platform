from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return ''
    # key is dimension id, we need to look up dim_{id}_a or _b? This filter is generic.
    # We'll try to handle if dictionary has dim_{key}_a
    # For template we used get_item but need more logic - simplify: if dictionary is dict and contains key directly
    if isinstance(dictionary, dict):
        # Try exact key
        if key in dictionary:
            return dictionary.get(key, '')
        # Try dim_{key}_a
        for suffix in [f'dim_{key}_a', f'dim_{key}_b']:
            if suffix in dictionary:
                # For simplicity return first found? But we need separate for A and B
                # We'll handle in template by using separate keys - so we need to support suffix
                pass
        # If key is like "dim_1_a" already, just return
        return dictionary.get(str(key), '')
    return ''

@register.filter
def get_dim_a(initial, dim_id):
    if not initial:
        return ''
    return initial.get(f'dim_{dim_id}_a', '')

@register.filter
def get_dim_b(initial, dim_id):
    if not initial:
        return ''
    return initial.get(f'dim_{dim_id}_b', '')
