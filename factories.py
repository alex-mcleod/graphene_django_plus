import channels_graphql_ws
import graphene
from graphene_django_extras import DjangoSerializerType as BaseDjangoSerializerType

# from graphene_django_subscriptions.subscription import Subscription
from rest_framework_filters.filterset import FilterSet

from .permissions import Permission
from .serializers import ModelMutationSerializer
from .types import PermissionedType
from .mutations import PermissionedDeletionMutation, PermissionedSerializerMutation
from .node import PermissionedConnectionField, PermissionedNode
from .utils import (
    create_permissioned_connection_field_for_type,
    create_permissioned_node_field_for_type,
)

LIST_FIELD_FORMAT = "{type_name}___List"
RETRIEVE_FIELD_FORMAT = "{type_name}___Item"
CREATE_MUTATION_FIELD = "{type_name}___Create"
UPDATE_MUTATION_FIELD = "{type_name}___Update"
DELETE_MUTATION_FIELD = "{type_name}___Delete"


def make_mutation_class(**kwargs):

    type_name = f"CreateOrUpdate{kwargs['model'].__name__}Mutation"

    class Meta:
        name = type_name
        output_type = kwargs["output"]
        edge_output_type = kwargs["edge_output"]
        serializer_class = kwargs["serializer_class"]
        permission_class = kwargs["permission_class"]
        model_operations = kwargs["operation_names"]

    MutationType = type(type_name, (PermissionedSerializerMutation,), {"Meta": Meta})
    return MutationType


def make_delete_mutation_class(**kwargs):

    type_name = f"Delete{kwargs['model'].__name__}Mutation"

    class Meta:
        name = type_name
        model = kwargs.get("model")
        # output_type = kwargs["output"]
        # serializer_class = kwargs["serializer_class"]
        permission_class = kwargs["permission_class"]

    MutationType = type(type_name, (PermissionedDeletionMutation,), {"Meta": Meta})
    return MutationType


def make_subscription_class(**kwargs):
    type_name = f"{kwargs['model'].__name__}Subscription"

    SubscriptionType = type(
        type_name,
        (channel_graphql_ws.Subscription,),
        {"Meta": Meta, "event": graphene.String(), "node": kwargs["node_class"]},
    )
    return SubscriptionType


class PermissionedSchemaFieldsFactory(object):

    """ Used to simplify the process of generating mutation and query 
    fields for a given GraphQL type. Usage of this class is optional, but 
    it reduces the number of classes you need to write to add a new type to 
    the API, plus all the fields it generates use standard naming conventions
    to ensure the API is consistent. 
    
    The most useful class methods are QueryFieldsClass and MutationFieldsClass. 
    QueryFieldsClass will return a class with a {type}___List field for retrieving
    many `type` instances plus a {type}__Get field for retrieving a single
    `type` instance. MutationFieldsClass will return a mutation class with a 
    {type}__Create, {type}__Update and {type}__Delete fields depending on the
    allowed operations specified in `mutation_operations`. 
    
    You can subclass any factory generated class to add additional fields relating
    to querying or mutating a given type. """

    type_class: PermissionedType
    mutation_serializer_class: ModelMutationSerializer
    mutation_operations: list

    @classmethod
    def _get_or_make(cls, attr_name, make_func):
        if not getattr(cls, attr_name, None):
            setattr(cls, attr_name, make_func())
        return getattr(cls, attr_name)

    @classmethod
    def get_model(cls):
        return cls.OutputTypeClass()._meta.model

    @classmethod
    def OutputTypeClass(cls):
        return cls.type_class

    @classmethod
    def PermissionClass(cls):
        return cls.OutputTypeClass().permission_class

    @classmethod
    def ListField(cls, *args, **kwargs):
        return cls._get_or_make(
            "_list_field",
            lambda: create_permissioned_connection_field_for_type(
                cls.OutputTypeClass()
            ),
        )

    @classmethod
    def ListEdgeType(cls):
        return cls.ListField().type.Edge

    @classmethod
    def RetrieveField(cls, *args, **kwargs):
        return cls._get_or_make(
            "_retrieve_field",
            lambda: create_permissioned_node_field_for_type(
                cls.OutputTypeClass(), *args, **kwargs
            ),
        )

    @classmethod
    def QueryFieldsClass(cls):
        type_name = cls.get_model().__name__
        list_field_name = LIST_FIELD_FORMAT.format(type_name=type_name)
        retrieve_field_name = RETRIEVE_FIELD_FORMAT.format(type_name=type_name)

        class Query(graphene.ObjectType):
            pass

        # Add list resolver
        setattr(Query, list_field_name, cls.ListField())

        # Add single node resolver
        setattr(Query, retrieve_field_name, cls.RetrieveField())

        return Query

    @classmethod
    def CreateAndUpdateMutationClass(cls):
        return cls._get_or_make(
            "_mutation_class",
            lambda: make_mutation_class(
                model=cls.get_model(),
                output=cls.OutputTypeClass(),
                edge_output=cls.ListField().type.Edge,
                serializer_class=cls.mutation_serializer_class,
                permission_class=cls.PermissionClass(),
                operation_names=cls.mutation_operations,
            ),
        )

    @classmethod
    def DeleteMutationClass(cls):
        return cls._get_or_make(
            "_delete_mutation_type",
            lambda: make_delete_mutation_class(
                model=cls.get_model(), permission_class=cls.PermissionClass()
            ),
        )

    @classmethod
    def MutateField(cls):
        return cls.MutationClass().Field()

    @classmethod
    def MutationFieldsClass(cls):
        if cls.mutation_operations:
            assert (
                cls.mutation_serializer_class
            ), "If mutation_operations are defined, you must also define a mutation_serializer_class."
        type_name = cls.get_model().__name__

        class Mutation(graphene.ObjectType):
            pass

        # Add mutation field
        if "create" in cls.mutation_operations:
            create_mutation_field_name = CREATE_MUTATION_FIELD.format(
                type_name=type_name
            )
            setattr(
                Mutation,
                create_mutation_field_name,
                cls.CreateAndUpdateMutationClass().Field(),
            )

        if "update" in cls.mutation_operations:
            update_mutation_field_name = UPDATE_MUTATION_FIELD.format(
                type_name=type_name
            )
            setattr(
                Mutation,
                update_mutation_field_name,
                cls.CreateAndUpdateMutationClass().Field(),
            )

        if "delete" in cls.mutation_operations:
            delete_mutation_field_name = DELETE_MUTATION_FIELD.format(
                type_name=type_name
            )
            setattr(
                Mutation, delete_mutation_field_name, cls.DeleteMutationClass().Field()
            )

        return Mutation
