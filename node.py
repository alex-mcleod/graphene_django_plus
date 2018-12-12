from functools import partial

import graphene
from graphene.relay.node import AbstractNode, Node
from graphene.types.utils import get_type

from .connections import PermissionedConnectionField


class PermissionedNode(Node):

    """ Applies `can_view` method of permission_class during node access. Also uses
    database ID instead of global ID (unlike Relay Node, which gives a globally
    unique ID to each instance.).
    """

    id = graphene.Int()

    @classmethod
    def get_node_from_global_id(cls, info, global_id, only_type=None):
        assert only_type, "PermissionedNode requres only_type to be specified"

        # We make sure the ObjectType implements the "Node" interface
        if cls not in only_type._meta.interfaces:
            return None

        node = only_type.get_node(info, global_id)

        return node

    @classmethod
    def from_global_id(cls, global_id):
        raise NotImplementedError("from_global_id has yet to be implemented")

    @staticmethod
    def to_global_id(type, id):
        return id
