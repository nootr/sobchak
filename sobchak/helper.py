import logging
import yaml

def sigmoid(x):
    """sigmoid

    A sigmoid-like function.
    """
    return x / (1 + abs(x))

def get_object_by_id(objects, identifier):
    """get_object_by_id

    Returns the object which belongs to the given ID. Returns None if it wasn't
    found.
    """
    logging.debug('Searching for %s inside %s', identifier, objects)
    for obj in objects:
        if obj.id == identifier or obj.name == identifier:
            return obj
    logging.info('Could not find %s inside %s', identifier, objects)
    return None

def parse_config(filename):
    """parse_config

    Load a certain YAML-file and return its contents as a dictionary.
    """
    try:
        with open(filename, 'r') as config:
            return yaml.safe_load(config)
    except Exception as e:
        logging.error('Could not load %s: %s', filename, e)
        exit(1)
