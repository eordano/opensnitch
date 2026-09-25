"""Small filter grammar; only known columns and escaped literals reach SQL."""
import re


class FilterError(ValueError):
    pass


TOKEN = re.compile(r'\s*("(?:""|[^"\n])*"|\'(?:\'\'|[^\'\n])*\'|>=|<=|!=|<>|!~|&&|\|\||[():=<>!~&,]|[^\s():=<>!~&,|\'"]+)')


def compile_filter(text, columns, convert=None):
    tokens = []
    pos = 0
    while pos < len(text.rstrip()):
        match = TOKEN.match(text, pos)
        if not match:
            raise FilterError('Unexpected character near ' + text[pos:pos+12])
        tokens.append(match[1]); pos = match.end()
    pos = 0

    def peek():
        return tokens[pos].upper() if pos < len(tokens) else ''

    def take():
        nonlocal pos
        if pos >= len(tokens):
            raise FilterError('Expected a value or closing parenthesis')
        value = tokens[pos]; pos += 1
        return value

    def literal(key):
        value = take()
        if value in ('(', ')', ',', '=', ':', '!', '<', '>', '>=', '<=', '!=', '<>', '&&', '||'):
            raise FilterError('Expected a value after ' + key)
        if value[:1] not in ('"', "'"):
            while peek() == ':':
                take(); value += ':' + take()
        if value[:1] in ('"', "'"):
            quote = value[0]; value = value[1:-1].replace(quote+quote, quote)
        if convert:
            value = convert(key, value)
        return str(value)

    def sql(value):
        return "'" + value.replace("'", "''") + "'"

    def atom():
        if peek() in ('!', 'NOT'):
            take(); return '(NOT ' + atom() + ')'
        if peek() == '(':
            take(); result = expr()
            if take() != ')': raise FilterError('Expected closing parenthesis')
            return '(' + result + ')'
        key = take().lower()
        column = columns.get(key)
        if column is None: raise FilterError('Unknown or unavailable field: ' + key)
        op = take().upper()
        if op == 'IN':
            if take() != '(': raise FilterError('Expected ( after IN')
            values = [sql(literal(key))]
            while peek() == ',':
                take(); values.append(sql(literal(key)))
            if take() != ')': raise FilterError('Expected ) after list')
            return column + ' IN (' + ','.join(values) + ')'
        if op not in (':', '=', '!=', '<>', '<', '>', '<=', '>=', '~', '!~'):
            raise FilterError('Expected :, =, !=, <>, <, >, <=, >= or ~ after ' + key)
        value = literal(key)
        if op in ('<', '>', '<=', '>='):
            if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
                raise FilterError('Range comparisons require a number')
            return 'CAST(' + column + ' AS NUMERIC) ' + op + ' ' + value
        if op in ('~', '!~'):
            value = value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            return column + (' NOT LIKE ' if op == '!~' else ' LIKE ') + sql('%'+value+'%') + " ESCAPE '\\'"
        return column + ('=' if op == ':' else op) + sql(value)

    def conjunction():
        result = atom()
        while peek() and peek() not in (')', 'OR', '||', ','):
            if peek() in ('AND', '&&'): take()
            result = '(' + result + ' AND ' + atom() + ')'
        return result

    def expr():
        result = conjunction()
        while peek() in ('OR', '||'):
            take(); result = '(' + result + ' OR ' + conjunction() + ')'
        return result

    if not tokens: return ''
    result = expr()
    if pos != len(tokens): raise FilterError('Unexpected token: ' + tokens[pos])
    return result
