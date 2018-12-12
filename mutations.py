import graphene
from graphql.error import GraphQLError
from graphene.relay.mutation import ClientIDMutation
from graphene_django.rest_framework.mutation import (
    ErrorType,
    Field,
    InputField,
    SerializerMutationOptions,
    fields_for_serializer,
    get_object_or_404,
    yank_fields_from_attrs,
)

from .connections import OrderByField, get_paginator_for_queryset
from .node import PermissionedNode
from .utils import get_fields

EDGE_ORDER_BY_INPUT_FIELD = "edge_cursor_order_by"


def _raise_permission_error():
    raise GraphQLError("You do not have permission to perform this mutation")


class PermissionedSerializerMutation(ClientIDMutation):

    """ 
    Generates a mutation definition using a `serializer_class`, `output_type` and `permission_class`
    (among other, optional arguments). The `serializer_class` is used to validate input,
    while `output_type` is used to "serialize" the resulting object if it is successfully created.
    `permission_class` is used to determine with a given user is permitted to perform a particular 
    mutation. 
    
    Note: This base class is heavily based on the SeralizerMutation class in the graphene_django package. 
    Unfortunately, that class did not allow you to use an existing DjangoObjectType as output,
    so this version was created. See 
    """

    class Meta:
        abstract = True

    errors = graphene.List(
        ErrorType, description="May contain more than one error for same field."
    )
    ok = graphene.Boolean(required=True)

    @classmethod
    def __init_subclass_with_meta__(
        cls,
        permission_class=None,
        output_type=None,
        edge_output_type=None,
        lookup_field=None,
        serializer_class=None,
        model_class=None,
        model_operations=["create", "update"],
        only_fields=(),
        exclude_fields=(),
        **options,
    ):
        assert (
            permission_class
        ), "A permission class is required when using PermissionedSerializerMutation."

        assert (
            output_type
        ), "An output type is required when using PermissionedSerializerMutation."

        cls.permission_class = permission_class
        cls.output_type = output_type
        cls.edge_output_type = edge_output_type

        if not serializer_class:
            raise Exception("serializer_class is required for the SerializerMutation")

        if "update" not in model_operations and "create" not in model_operations:
            raise Exception('model_operations must contain "create" and/or "update"')

        serializer = serializer_class()
        if model_class is None:
            serializer_meta = getattr(serializer_class, "Meta", None)
            if serializer_meta:
                model_class = getattr(serializer_meta, "model", None)

        if lookup_field is None and model_class:
            lookup_field = model_class._meta.pk.name

        input_fields = fields_for_serializer(
            serializer, only_fields, exclude_fields, is_input=True
        )

        _meta = SerializerMutationOptions(cls)
        _meta.lookup_field = lookup_field
        _meta.model_operations = model_operations
        _meta.serializer_class = serializer_class
        _meta.model_class = model_class

        # Resulting schema type will have a "result" value which will be set
        # if the object is successfully created. Will also have an "edge" value
        # which can be used instead of "result" if trying to add new object
        # to existing connection
        _meta.fields = {
            "result": graphene.Field(output_type),
            "edge": graphene.Field(edge_output_type),
        }

        input_fields = yank_fields_from_attrs(input_fields, _as=InputField)

        if "update" in model_operations:
            input_fields["id"] = graphene.GlobalID(required=False)
        else:
            input_fields.pop("id")

        input_fields[EDGE_ORDER_BY_INPUT_FIELD] = OrderByField(required=False)

        super(PermissionedSerializerMutation, cls).__init_subclass_with_meta__(
            _meta=_meta, input_fields=input_fields, **options
        )

    @classmethod
    def get_serializer_kwargs(cls, root, info, **input):
        lookup_field = cls._meta.lookup_field
        model_class = cls._meta.model_class

        if model_class:
            if "update" in cls._meta.model_operations and lookup_field in input:
                id_val = input[lookup_field]
                instance = model_class.objects.filter(id=id_val).first()
                if not instance:
                    raise Exception(
                        f"{model_class} instance with ID {id_val} does not exist."
                    )
            elif "create" in cls._meta.model_operations:
                instance = None
            else:
                raise Exception(
                    'Invalid update operation. Input parameter "{}" required.'.format(
                        lookup_field
                    )
                )

            return {
                "instance": instance,
                "data": input,
                "context": {"request": info.context},
            }

        return {"data": input, "context": {"request": info.context}}

    @classmethod
    def mutate_and_get_payload(cls, root, info, **input):
        requested_fields = get_fields(info)
        if requested_fields.get("edge") and not input.get(EDGE_ORDER_BY_INPUT_FIELD):
            raise Exception(
                "You cannot request the `edge` field without also specifying an ordering value using `edgeCursorOrderBy` in the mutation input. Otherwise, the mutation handler does not know how to compute the cursor for the resulting edge."
            )
        kwargs = cls.get_serializer_kwargs(root, info, **input)
        serializer = cls._meta.serializer_class(**kwargs)

        if serializer.is_valid():
            return cls.perform_mutate(serializer, info, **input)
        else:
            errors = [
                ErrorType(field=key, messages=value)
                for key, value in serializer.errors.items()
            ]

            return cls(errors=errors, ok=False)

    @classmethod
    def _get_edge(cls, obj, ordering):
        paginator = get_paginator_for_queryset(
            cls._meta.model_class.objects.all(), ordering=ordering
        )
        cursor = paginator.cursor(obj)
        edge = cls.edge_output_type(node=obj, cursor=cursor)
        return edge

    @classmethod
    def _save_and_get_payload(cls, serializer, **input):
        obj = serializer.save()
        # Value for EDGE_ORDER_BY_INPUT_FIELD is required if
        # edge is a requested field, but otherwise it is optional.
        # Validation for this happens in `mutate_and_get_payload`
        ordering = input.get(EDGE_ORDER_BY_INPUT_FIELD)
        if ordering:
            edge = cls._get_edge(obj, ordering)
        else:
            edge = None
        return cls(errors=None, result=obj, edge=edge, ok=True)

    @classmethod
    def perform_mutate(cls, serializer, info, **input):
        obj = serializer.instance or serializer.build_obj()
        perm_inst = cls.permission_class()
        perm_inst.queryset = obj.__class__.objects.all()
        has_permission = False
        if obj.id:
            # This is an update
            has_permission = perm_inst.can_change(info.context.user, obj)
        else:
            # This is creation
            has_permission = perm_inst.can_add(info.context.user, obj)
        if not has_permission:
            _raise_permission_error()

        return cls._save_and_get_payload(serializer, **input)


class DeletionInput(graphene.InputObjectType):
    id = graphene.Int(required=True)


class PermissionedDeletionMutation(graphene.Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, permission_class=None, model=None, **options):
        assert (
            permission_class
        ), "A permission class is required when using PermissionedDeletionMutation."
        assert model, "A model is required when using PermissionedDeletionMutation"
        cls.permission_class = permission_class
        cls.model = model
        super().__init_subclass_with_meta__(**options)

    class Meta:
        abstract = True

    class Arguments:
        input = DeletionInput(required=True)

    ok = graphene.Boolean(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        ok = True
        model_class = cls.model
        obj = model_class.objects.filter(id=input.id).first()
        if not obj:
            raise Exception(
                f"{model_class} instance with ID {input.id} does not exist."
            )
        perm_inst = cls.permission_class()
        perm_inst.queryset = model_class.objects.all()
        can_delete = perm_inst.can_delete(info.context.user, obj)
        if not can_delete:
            _raise_permission_error()
        obj.delete()
        return cls(ok=ok)
