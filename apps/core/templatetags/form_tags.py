from django import template


register = template.Library()


@register.inclusion_tag("core/components/form_field.html")
def form_field(field, autocomplete="", placeholder=""):
    widget = field.field.widget
    widget_name = widget.__class__.__name__
    input_type = getattr(widget, "input_type", "")
    is_choice_group = widget_name in {"RadioSelect", "CheckboxSelectMultiple"}
    is_checkbox = input_type == "checkbox" and not is_choice_group

    described_by = []
    if field.help_text:
        described_by.append(f"{field.auto_id}_helptext")
    if field.errors:
        described_by.append(f"{field.auto_id}_error")

    attrs = {}
    existing_class = widget.attrs.get("class", "")
    if not field.is_hidden and not is_checkbox and not is_choice_group:
        attrs["class"] = " ".join(filter(None, (existing_class, "form__control")))
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)
    if field.errors:
        attrs["aria-invalid"] = "true"
        attrs["aria-errormessage"] = f"{field.auto_id}_error"
    if field.field.required:
        attrs["aria-required"] = "true"
    if autocomplete:
        attrs["autocomplete"] = autocomplete
    if placeholder:
        attrs["placeholder"] = placeholder

    return {
        "field": field,
        "widget": field.as_widget(attrs=attrs),
        "is_checkbox": is_checkbox,
        "is_choice_group": is_choice_group,
    }
