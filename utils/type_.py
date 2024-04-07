from typing import Any, Union, TYPE_CHECKING

def type_checking(var: Any, type_: Union[type, tuple[type]], *indexed_types: Union[type, tuple[type]], use_attr: bool = False, raise_error: bool = TYPE_CHECKING, **named_types: Union[type, tuple[type]]):
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
    if not isinstance(var, type_):
        if raise_error:
            if isinstance(type_, tuple):
                raise TypeError(f"Expected type {', '.join([type_.__name__ for type_ in type_])}, got {type(var).__name__}")
            raise TypeError(f"Expected type {type_.__name__}, got {type(var).__name__}")
    for index, type_ in enumerate(indexed_types):
        if not isinstance(var, type_):
            if raise_error:
                if isinstance(type_, tuple):
                    raise TypeError(f"Expected type {', '.join([type_.__name__ for type_ in type_])} for value at index {index}, got {type(var).__name__}")
                raise TypeError(f"Expected type {type_.__name__} for value at index {index}, got {type(var).__name__}")
    if use_attr:
        for attr, type_ in named_types.items():
            try:
                if not isinstance(getattr(var, attr), type_):
                    if raise_error:
                        if isinstance(type_, tuple):
                            raise TypeError(f"Expected type {', '.join([type_.__name__])} for attribute {attr}, got {type(getattr(var, attr)).__name__}")
                        raise TypeError(f"Expected type {type_.__name__} for attribute {attr}, got {type(getattr(var, attr)).__name__}")
            except AttributeError as e:
                if isinstance(type_, tuple):
                    raise TypeError(f"Expected type {', '.join([type_.__name__])} for attribute {attr}, got nothing") from e
                raise TypeError(f"Expected type {type_.__name__} for attribute {attr}, got nothing") from e
    else:
        for attr, type_ in named_types.items():
            try:    
                if not isinstance(var[attr], type_):
                    if raise_error:
                        if isinstance(type_, tuple):
                            raise TypeError(f"Expected type {', '.join([type_.__name__])} for value at key {attr}, got {type(var[attr]).__name__}")
                        raise TypeError(f"Expected type {type_.__name__} for value at key {attr}, got {type(var[attr]).__name__}")
            except KeyError as e:
                if isinstance(type_, tuple):
                    raise TypeError(f"Expected type {', '.join([type_.__name__])} for value at key {attr}, got nothing") from e
                raise TypeError(f"Expected type {type_.__name__} for value at key {attr}, got nothing") from e