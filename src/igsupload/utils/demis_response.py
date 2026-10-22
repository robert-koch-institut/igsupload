

def extract_param(parameters, name):
    """
    Hilfsfunktion: Extrahiert einen Parameterwert aus der Demis-Response-Liste.
    """
    for param in parameters:
        if param.get('name') == name:
            value_identifier = param.get('valueIdentifier')
            if value_identifier and 'value' in value_identifier:
                return value_identifier['value']
    return None