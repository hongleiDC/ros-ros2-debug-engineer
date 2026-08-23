# ROS Noetic Python 3.8 Compatibility

ROS Noetic commonly runs on Ubuntu 20.04 with Python 3.8. Helper scripts in this branch should avoid syntax that requires newer Python versions.

## Avoid

- `str | None`
- `list[str]`
- `dict[str, Any]` when runtime compatibility is required without postponed evaluation support
- structural pattern matching (`match/case`)
- newer standard-library APIs without compatibility checks

## Prefer

- `Optional[str]`
- `List[str]`
- `Dict[str, Any]`
- `typing` imports when annotations are evaluated at runtime

## Validation target

The branch should keep scripts runnable on:

- Python 3.8 (Noetic baseline)
- Python 3.10+

New scripts should be checked with a Python 3.8 syntax parser before merging.
