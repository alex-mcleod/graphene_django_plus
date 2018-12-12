from django.contrib.auth.models import Group, Permission, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

import graphene
from graphql.error import GraphQLError

from .. import types, factories, serializers, permissions, filters

""" 
Integration tests which use the Group model to create a basic schema and
then test queries and mutations.
"""

DISALLOW_CREATION = "disallow_creation"


class GroupPermission(permissions.Permission):
    def can_add(self, user, obj):
        return obj.name != DISALLOW_CREATION

    def get_viewable(self, user):
        return self.queryset.filter(user=user)

    def get_changeable(self, user):
        return self.queryset.filter(user=user)

    def get_deletable(self, user):
        return self.queryset.filter(user=user)


class GroupType(types.PermissionedType):
    class Meta:
        model = Group
        permission_class = GroupPermission
        filterset_class = filters.deprecated_create_filter_class(Group, "name")


class GroupMutationSerializer(serializers.ModelMutationSerializer):
    class Meta:
        model = Group
        fields = ["name"]


class GroupSchemaFieldsFactory(factories.PermissionedSchemaFieldsFactory):
    type_class = GroupType
    mutation_serializer_class = GroupMutationSerializer
    mutation_operations = ["create", "update", "delete"]


class PermissionModelPermission(permissions.Permission):
    def can_add(self, user, obj):
        return True

    def get_viewable(self, user):
        return self.queryset.all()

    def get_changeable(self, user):
        return self.queryset.all()

    def get_deletable(self, user):
        return self.queryset.all()


class PermissionModelType(types.PermissionedType):
    class Meta:
        model = Permission
        permission_class = PermissionModelPermission
        filterset_class = filters.deprecated_create_filter_class(Permission, "codename")


class PermissionModelMutationSerializer(serializers.ModelMutationSerializer):
    class Meta:
        model = Permission
        fields = ["name", "codename", "content_type"]
    
    # content_type = serializers.PrimaryKeyRelatedField(
    #     queryset=ContentType.objects.all()
    # )
    



class PermissionModelSchemaFieldsFactory(factories.PermissionedSchemaFieldsFactory):
    type_class = PermissionModelType
    mutation_serializer_class = PermissionModelMutationSerializer
    mutation_operations = ["create", "update", "delete"]


class ContentTypePermission(permissions.Permission):
    def can_add(self, user, obj):
        return False

    def get_viewable(self, user):
        return self.queryset.none()

    def get_changeable(self, user):
        return self.queryset.none()

    def get_deletable(self, user):
        return self.queryset.none()


class ContentTypeType(types.PermissionedType):
    class Meta:
        model = ContentType
        permission_class = ContentTypePermission


class ContentTypeMutationSerializer(serializers.ModelMutationSerializer):
    class Meta:
        model = Permission
        fields = ["name", "codename"]


class ContentTypeSchemaFieldsFactory(factories.PermissionedSchemaFieldsFactory):
    type_class = ContentTypeType
    mutation_serializer_class = ContentTypeMutationSerializer
    mutation_operations = ["create", "update", "delete"]


class Query(
    GroupSchemaFieldsFactory.QueryFieldsClass(),
    PermissionModelSchemaFieldsFactory.QueryFieldsClass(),
):
    pass


class Mutation(
    GroupSchemaFieldsFactory.MutationFieldsClass(),
    PermissionModelSchemaFieldsFactory.MutationFieldsClass(),
):
    pass


test_schema = graphene.Schema(query=Query, mutation=Mutation)
