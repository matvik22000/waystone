import logging
import re
import typing as tp

_link_re = re.compile(r"`\[(.*?)]")


def extract_links(address: str, page: str) -> tp.Tuple[tp.List[str], tp.List[str]]:
    links = _link_re.findall(page)
    internal, external = set(), set()
    for link in links:
        link = parse_link_block(link)
        if ":" not in link:
            continue
        if is_external(link):
            external.add(link)
        else:
            internal.add(address + link)
    return list(internal), list(external)


def parse_link_block(link: str):
    seps = link.count("`")
    if seps == 0:
        return link
    elif seps == 1:
        # labeled link`72914442a3689add83a09a767963f57c:/page/index.mu
        return link.split("`")[1]
    elif seps == 2:
        # Query the System`:/page/fields.mu`username|auth_token|action=view|amount=64
        # leave params, some links may not work without them
        addr, url, params = link.split("`")
        if params.startswith("*"):
            # trash
            return url
        return url + "`" + params
    else:
        raise ValueError("unable to parse link %s" % link)


def is_external(link: str) -> bool:
    """
    external - lead to page on another node

    :param link:
    :return:
    """
    return not link.startswith(":")
