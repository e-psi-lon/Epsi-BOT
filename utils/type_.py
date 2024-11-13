from typing import Any, Union, TYPE_CHECKING

__all__ = ["type_checking"]

def type_checking(var: Any, type_: Union[type, tuple[type]], *indexed_types: Union[type, tuple[type]],
                  use_attr: bool = False, raise_error: bool = TYPE_CHECKING, **named_types: Union[type, tuple[type]]):
    """
    Check the types of a variable and its attributes/values

    Parameters
    ----------
    var : Any
        The variable to check
    type_ : Union[type, tuple[type]]
        The type of the variable to check
    indexed_types : Union[type, tuple[type]]
        The types of the indexed values of the variable
    use_attr : bool
        Whether to check the attributes or the values of the variable. Default is False
    raise_error : bool
        Whether to raise an error if the variable doesn't match the types. Default is False
    named_types : Union[type, tuple[type]] 
        The types of the named attributes or values of the variable

    Raises
    ------
    TypeError
        If the variable doesn't match the types
    """

    def raise_type_error(expected_type: Union[type, tuple[type]], actual_type: type, identifier: str = None,
                         from_error: Exception = None):
        if isinstance(expected_type, tuple):
            expected_type_names = ', '.join([type__.__name__ for type__ in expected_type])
        else:
            expected_type_names = expected_type.__name__
        if identifier is not None:
            error_message = f"Expected type {expected_type_names} for {identifier}, got {actual_type.__name__}"
        else:
            error_message = f"Expected type {expected_type_names}, got {actual_type.__name__}"
        if from_error is not None:
            raise TypeError(error_message) from from_error
        else:
            raise TypeError(error_message)

    if not isinstance(var, type_) and raise_error:
        raise_type_error(type_, type(var))
    for index, type_ in enumerate(indexed_types):
        if not isinstance(var, type_) and raise_error:
            raise_type_error(type_, type(var), f"value at index {index}")
    if use_attr:
        for attr, type_ in named_types.items():
            try:
                attr_value = getattr(var, attr)
                if not isinstance(attr_value, type_) and raise_error:
                    raise_type_error(type_, type(attr_value), f"attribute {attr}")
            except AttributeError as e:
                if raise_error:
                    raise_type_error(type_, type(None), f"attribute {attr}", from_error=e)
    else:
        for attr, type_ in named_types.items():
            try:
                value = var[attr]
                if not isinstance(value, type_) and raise_error:
                    raise_type_error(type_, type(value), f"value at key {attr}")
            except KeyError as e:
                if raise_error:
                    raise_type_error(type_, type(None), f"value at key {attr}", from_error=e)
