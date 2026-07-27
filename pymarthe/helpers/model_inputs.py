"""
Contains helper functions to write MARTHE model inputs (grids and lists)
from a single configuration file.

A configuration file (YAML or JSON) describes, property by property, one or
more "set" operations mapping a value onto a subset of the property (selected
by layer, nested grid, timestep, zone, boundname, ...). The helper:

    1. loads the MARTHE model with PyMarthe (`MartheModel`),
    2. loads each required property,
    3. applies every set operation on the matching property object
       (`MartheField` for grid-like properties, `MarthePump` / `MartheSoil`
        for list-like properties),
    4. writes the updated properties back into the MARTHE input files on disk.

This provides a lightweight, declarative way to populate a model without
writing python for every property, and complements the PEST-oriented
`MartheModel.from_config()` (which reads parameter files produced by
`MartheOptim`).

Supported properties
--------------------
    - grid-like (MartheField)  : 'permh', 'emmca', 'emmli', 'kepon', ...
                                 (any field property available in the model)
    - list-like  (MarthePump)  : 'aqpump', 'rivpump'
    - list-like  (MartheSoil)  : 'soil'

Configuration file (YAML) example
---------------------------------
    model:
      rma: Didact3.rma          # path to the .rma file (relative to this file)
      spatial_index: false      # optional (bool or path), default false

    inputs:

      # grid-like property : selectors are `layer` and `inest`
      - property: permh
        use_imask: true         # optional MartheField argument (default true)
        set:
          - {value: 1.0e-3, layer: 0}
          - {value: 5.0e-4, layer: [1, 2]}

      # list-like pumping : selectors are istep, node, layer, i, j, boundname
      - property: aqpump
        set:
          - {value: -50.0, boundname: [p1, p2], istep: 0}
          - {value: -12.4, layer: 0, i: 33, j: 18}

      # list-like soil : `soilprop` is required, selectors are istep and zone
      - property: soil
        set:
          - {soilprop: cap_sol_progr, value: 34.6, zone: [1, 2]}

Usage
-----
    # python API
    from pymarthe.helpers.model_inputs import write_model_inputs
    mm = write_model_inputs('model_inputs.yaml')

    # command line
    python -m pymarthe.helpers.model_inputs model_inputs.yaml
"""

import os
import json
import argparse


# ---- Property names implemented as list-like objects in PyMarthe
LIST_PROPS = ('aqpump', 'rivpump', 'soil')

# ---- Selector keys accepted for each property style (besides 'value')
FIELD_KEYS = ('layer', 'inest')
PUMP_KEYS = ('istep', 'node', 'layer', 'i', 'j', 'boundname')
SOIL_KEYS = ('soilprop', 'istep', 'zone')




def _resolve(path, base):
    """
    Resolve a (possibly relative) path against a base directory.
    Absolute paths are returned unchanged. Relative paths are joined to
    `base` (typically the configuration file directory) so that a config
    file is self-contained and can be run from any working directory.
    """
    if path is None:
        return None
    path = os.path.normpath(str(path))
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base, path))




def _coerce_value(value):
    """
    Coerce a set value to a number when possible (e.g. '1.0e-3' -> 0.001).
    Non-numeric strings (unlikely for a value) are returned unchanged.
    """
    if isinstance(value, bool):
        # avoid the bool-is-int surprise, keep as is
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value




def read_inputs_config(configfile):
    """
    Read a model-inputs configuration file (YAML or JSON).

    Parameters:
    ----------
    configfile (str) : path to the configuration file.
                       The format is inferred from the extension:
                          - '.yaml' / '.yml' : YAML  (requires `pyyaml`)
                          - '.json'          : JSON

    Returns:
    --------
    config (dict) : parsed configuration dictionary.

    Examples:
    --------
    config = read_inputs_config('model_inputs.yaml')
    """
    ext = os.path.splitext(configfile)[1].lower()
    with open(configfile, 'r') as f:
        if ext in ('.yaml', '.yml'):
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "Reading a YAML configuration file requires the `pyyaml` "
                    "package. Install it with `pip install pyyaml`, or provide "
                    "the configuration as a JSON ('.json') file."
                ) from e
            config = yaml.safe_load(f)
        elif ext == '.json':
            config = json.load(f)
        else:
            raise ValueError(
                "Unsupported configuration file extension '{}'. "
                "Use '.yaml', '.yml' or '.json'.".format(ext)
            )

    # ---- Minimal structural validation
    if not isinstance(config, dict):
        raise ValueError(
            "Invalid configuration : the top-level content must be a mapping "
            "with 'model' and 'inputs' keys.")
    if 'model' not in config or not isinstance(config['model'], dict):
        raise ValueError("Invalid configuration : a 'model' mapping is required.")
    if 'rma' not in config['model']:
        raise ValueError(
            "Invalid configuration : model['rma'] (path to the .rma file) "
            "is required.")
    if 'inputs' not in config or not isinstance(config['inputs'], list):
        raise ValueError(
            "Invalid configuration : an 'inputs' list is required.")

    return config




def _get_sets(block):
    """
    Extract the list of set operations from an input block.
    Accepts the 'set' (preferred) or 'sets' key, and tolerates a single
    mapping instead of a list.
    """
    sets = block.get('set', block.get('sets'))
    prop = block.get('property', '?')
    if sets is None:
        raise ValueError(
            "Input block for property '{}' has no 'set' operations.".format(prop))
    if isinstance(sets, dict):
        sets = [sets]
    if not isinstance(sets, list) or len(sets) == 0:
        raise ValueError(
            "The 'set' entry for property '{}' must be a non-empty list "
            "of operations.".format(prop))
    return sets




def _check_keys(s, allowed, prop):
    """
    Ensure a set operation only contains supported keys for the given
    property, raising an explicit error on typos (e.g. 'boundnames').
    """
    allowed = set(allowed) | {'value'}
    extra = set(s) - allowed
    if extra:
        raise ValueError(
            "Unsupported key(s) {} in a 'set' operation for property '{}'. "
            "Allowed keys are : {}.".format(
                sorted(extra), prop, sorted(allowed)))
    if 'value' not in s:
        raise ValueError(
            "A 'set' operation for property '{}' is missing the required "
            "'value' key.".format(prop))




def _apply_set(prop, s, name):
    """
    Apply a single set operation to a loaded property object, dispatching
    on the property class (MartheField / MarthePump / MartheSoil).
    """
    # -- Local import to avoid any import-order/circular issue
    from pymarthe import MartheField, MarthePump, MartheSoil

    # ---- Grid-like property (MartheField)
    if isinstance(prop, MartheField):
        _check_keys(s, FIELD_KEYS, name)
        prop.set_data(_coerce_value(s['value']),
                      layer=s.get('layer'),
                      inest=s.get('inest'))

    # ---- List-like pumping (MarthePump)
    elif isinstance(prop, MarthePump):
        _check_keys(s, PUMP_KEYS, name)
        prop.set_data(_coerce_value(s['value']),
                      istep=s.get('istep'),
                      node=s.get('node'),
                      layer=s.get('layer'),
                      i=s.get('i'),
                      j=s.get('j'),
                      boundname=s.get('boundname'))

    # ---- List-like soil (MartheSoil)
    elif isinstance(prop, MartheSoil):
        _check_keys(s, SOIL_KEYS, name)
        if 'soilprop' not in s:
            raise ValueError(
                "A 'set' operation for the 'soil' property requires a "
                "'soilprop' key (e.g. 'cap_sol_progr').")
        prop.set_data(soilprop=s['soilprop'],
                      value=_coerce_value(s['value']),
                      istep=s.get('istep'),
                      zone=s.get('zone'))

    else:
        raise TypeError(
            "Unsupported property object type for '{}' : {}.".format(
                name, type(prop).__name__))




def apply_model_inputs(mm, inputs, base='.', write=True, verbose=True):
    """
    Apply a list of input blocks to a (loaded) MartheModel and, optionally,
    write the updated properties on disk.

    Parameters:
    ----------
    mm (MartheModel) : model instance to modify.
    inputs (list) : list of input blocks (see module docstring for the
                    expected structure). Each block must contain a
                    'property' name and a 'set' list of operations.
    base (str, optional) : directory used to resolve relative output
                           filenames. Default is '.'.
    write (bool, optional) : whether to write the updated properties into
                             the MARTHE input files. Default is True.
    verbose (bool, optional) : print a short progress log. Default is True.

    Returns:
    --------
    touched (list) : names of the properties that were modified.

    Examples:
    --------
    apply_model_inputs(mm, config['inputs'])
    """
    touched = []

    for block in inputs:
        if 'property' not in block:
            raise ValueError("An input block is missing the 'property' key.")
        name = block['property']

        # ---- Determine whether this is a field (grid-like) property
        is_field = (name not in LIST_PROPS) and (name in mm.mlfiles)

        # ---- Load the property (only pass use_imask to fields)
        load_kwargs = {}
        if is_field and 'use_imask' in block:
            load_kwargs['use_imask'] = bool(block['use_imask'])
        mm.load_prop(name, **load_kwargs)

        # ---- Guard against unsupported property names
        if name not in mm.prop:
            raise ValueError(
                "Property '{}' is not supported by MartheModel.load_prop(). "
                "Expected a field property present in the model "
                "(e.g. 'permh', 'emmca', ...) or one of {}.".format(
                    name, list(LIST_PROPS)))

        prop = mm.prop[name]

        # ---- Apply every set operation
        sets = _get_sets(block)
        if verbose:
            print("\t-> Setting '{}' ({} operation(s))".format(name, len(sets)))
        for s in sets:
            _apply_set(prop, s, name)

        # ---- Write the updated property on disk
        if write:
            filename = _resolve(block.get('filename'), base)
            _write_prop(prop, name, filename)
            if verbose:
                dest = filename if filename is not None else 'model file(s)'
                print("\t   written to {}".format(dest))

        touched.append(name)

    return touched




def _write_prop(prop, name, filename=None):
    """
    Write a single property on disk, honouring an optional output filename
    for the property classes that support it (MartheField, MartheSoil).
    """
    from pymarthe import MarthePump

    if filename is None:
        prop.write_data()
    else:
        if isinstance(prop, MarthePump):
            raise ValueError(
                "A 'filename' override is not supported for pumping property "
                "'{}' : pumping data is written back into the .pastp / listm / "
                "record files referenced by the model.".format(name))
        # -- Make sure the output directory exists
        outdir = os.path.dirname(filename)
        if outdir and not os.path.isdir(outdir):
            os.makedirs(outdir, exist_ok=True)
        prop.write_data(filename=filename)




def write_model_inputs(configfile, mm=None, write=True, verbose=True):
    """
    Write MARTHE model inputs (grids and lists) from a configuration file.

    This is the main entry point : it reads the configuration, builds
    (or reuses) a MartheModel, applies every set operation described in the
    'inputs' section and writes the updated properties on disk.

    Parameters:
    ----------
    configfile (str) : path to the YAML/JSON configuration file.
    mm (MartheModel, optional) : an already loaded model to modify. If None
                                 (default), the model is built from the
                                 'model' block of the configuration.
    write (bool, optional) : whether to write the updated properties into the
                             MARTHE input files on disk. Default is True.
    verbose (bool, optional) : print a short progress log. Default is True.

    Returns:
    --------
    mm (MartheModel) : the (modified) MartheModel instance.

    Examples:
    --------
    from pymarthe.helpers.model_inputs import write_model_inputs
    mm = write_model_inputs('model_inputs.yaml')
    """
    from pymarthe import MartheModel

    # ---- Read and validate configuration
    config = read_inputs_config(configfile)
    base = os.path.dirname(os.path.abspath(configfile))

    # ---- Build the model if not provided
    if mm is None:
        model = config['model']
        rma = _resolve(model['rma'], base)
        si = model.get('spatial_index', False)
        # a spatial index given as a (relative) path is resolved too
        if isinstance(si, str) and si.lower() not in ('true', 'false', 'none'):
            si = _resolve(si, base)
        if verbose:
            print('WRITING MODEL INPUTS ...')
            print('\t-> Loading model {}'.format(rma))
        mm = MartheModel(rma, spatial_index=si)

    # ---- Apply and write the inputs
    apply_model_inputs(mm, config['inputs'], base=base,
                       write=write, verbose=verbose)

    if verbose:
        print('\t-> Done ({} propertie(s) updated).'.format(len(config['inputs'])))

    return mm




def main(argv=None):
    """
    Command line entry point.

    Examples:
    --------
    python -m pymarthe.helpers.model_inputs model_inputs.yaml
    python -m pymarthe.helpers.model_inputs model_inputs.yaml --no-write
    """
    parser = argparse.ArgumentParser(
        prog='write_model_inputs',
        description='Write MARTHE model inputs (grids and lists) from a '
                    'YAML/JSON configuration file using PyMarthe.')
    parser.add_argument('configfile',
                        help='path to the YAML/JSON configuration file.')
    parser.add_argument('--no-write', dest='write', action='store_false',
                        help='parse and apply the inputs without writing the '
                             'MARTHE files (dry run).')
    parser.add_argument('-q', '--quiet', dest='verbose', action='store_false',
                        help='suppress the progress log.')
    args = parser.parse_args(argv)

    write_model_inputs(args.configfile, write=args.write, verbose=args.verbose)




if __name__ == '__main__':
    main()
