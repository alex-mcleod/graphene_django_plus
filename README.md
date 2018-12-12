# Myagi Simple Graphene

## About

This module contains a series of functions, classes and class generators which
make it easier to add new types, connections and mutations to our GraphQL API.
Graphene itself is fairly unopionated, so conventions
are instead "baked in" to this module to ensure consistency across our API.
Many of these conventions are also taken from our existing DRF based API
and our SimpleAPI module, which makes it easier to migrate RESTful endpoints
over to a GraphQL based alternative.

## Key Features

- Permission management --> SimpleGraphene makes it possible to use
  PermissonClasses from our SimpleAPI module to determine which entities
  a given user can create, view, update and delete.

- Filtering --> The `deprecated_create_filter_class` function from our SimpleAPI module
  can be use to generate filter params for connections in our API.

- Schema Field Generation --> Whenever we add a new type to our GraphQL
  based API, we usually want to add certain fields to support certain operations,
  e.g. listing objects of that type, getting a specific instance of that type,
  creating a new instance, updating and deleting. SimpleGraphene generates query
  and mutation fields for these operations using standardized conventions. This simplifies
  the process of adding a new type to our API.

- Optional --> SimpleGraphene just offers a layer of abstraction over Graphene. You
  do not have to use it if you don't want to (though you still need to make sure you
  adhere to our API conventions). It is also possible to only partially use SimpleGraphene.

- Easier migration for existing Django Rest Framework based endpoints.

## Example

As an example, let's pretend we add a model called `Car`:

```python
# File: apps/car/models.py

class Car(models.Model):
    belongs_to_user = models.ForeignKey(User)
    model_name = models.CharField(max_length=32)
    manufacturer = models.ForeignKey(Manufacturer)
```

If we wanted to add this model to our GraphQL based API, we could do so using
Graphene and SimpleGraphene. We would need the following files / classes:

```python
# File: apps/car/api/permissions.py

from graphene_django_plus.permissions import Permission

class CarPermission(Permission):

    """ Defines the operations a given user can perform in relation to the
    Car model via the API. """

    def can_add(self, user, obj):
        """ Will get called with a user and the car object they are trying to create.
        Return `False` to prevent creation of the object, `True` to allow. """
        return True

    def get_viewable(self, user):
        """ Will get called with a `user` who is trying to access car instances via the
        API. `self.queryset` will be the queryset representing those cars. In this case,
        we filter the queryset further so that the user only gets access to car objects
        which belong to them. """
        return self.queryset.filter(
            belongs_to_user=user
        )

    def get_changeable(self, user):
        """ Called when a user tries to update a car / cars using a mutation. """
        return self.queryset.filter(
            belongs_to_user=user
        )

    def get_deletable(self, user):
        """ Called when a user tries to delete a car / cards using a mutation.
        In this case prevents deleting of any cars objects, including those which
        belong to the current user. """
        return self.queryset.none()
```

```python
# File: apps/car/api/schema.py

from graphene_django_plus import (connections, factories, mutations, types)

from .permissions import CarPermission

from ..models import Car

class CarType(types.PermissionedType):

    """ Represents the Car model when querying our GraphQL based API.
    We could add extra fields to this type, e.g. properties which appear
    on the Car model. See the Graphene docs for instructions on how to do this.  """

    class Meta:
        model = Car
        # Enables filtering car objects by the `manufacturer` field.
        filterset_class = deprecated_create_filter_class(Message, "manufacturer")
        # Ensures permission class gets used when cars are listed or a single instance is retrieved.
        permission_class = CarPermission

class CarMutationSerializer(serializers.ModelMutationSerializer):

    """ During a create or update mutation, this class will be used to convert
    the JSON based data sent to the server into a new model instance or changes to the existing
    car instance. Use the `fields` argument to restrict the set of fields which can be set / updated
    via the API. """

    class Meta:
        model = Car
        fields = '__all__'

class CarSchemaFieldsFactory(factories.PermissionedSchemaFieldsFactory):

    """ The SchemaFieldsFactory class is used to generate fields which
    "connect up" the CarType to the API. These fields then need to be included
    in the schema explicitly (this is done using the `Query` and `Mutation`)
    classes below. """

    output_type_class = CarType
    mutation_serializer_class = CarMutationSerializer

    # Technically, the `permission_class` can also control the permissable
    # mutation operations. This argument just determines which fields get
    # added to the mutation class generated by this factory.
    mutation_operations = ["create", "update", "delete"]

class Query(
    CarSchemaFieldsFactory.QueryFieldsClass()
):
    """ This Query class is what is ultimately included in the schema. It should
    include all the fields necessary to query the different types defined in
    this file. In this case, only the CarType is defined, so we generate these fields
    using the QueryFieldsClass class-method on the CarSchemaFieldsFactory. This
    will add the following fields to the Query class:

    Car__List --> Can be used to retrieve many cars. Takes arguments such as
    limit, offset, orderBy and any filterable fields. E.g. could be used like so:

    query {
        Car__List(limit: 10, offset: 0, orderBy: ['id'], manufacturer: 10) {
            edges {
                node {
                    modelName
                }
            }
        }
    }

    Car__Item --> Takes a single argument, ID, and returns the car with that ID.
    E.g. could be used like so:

    query {
        Car__Item(id: 55) {
            modelName
        }
    }


    """
    class Meta:
        abstract = True


class Mutation(
    CarSchemaFieldsFactory.MutationFieldsClass(),
):
    """ Similar to the Query class, this Mutation class is ultimately what
    is included in the schema. It should include all the mutation fields we want
    defined for the types in this file. Again, in this case we can just generate
    the mutation fields for the CarType using CarSchemaFieldsFactory.MutationFieldsClass()
    method. Including this Mutation class in the schema will make the following
    mutation operations available:

    Car__Create --> Used to create a new car instance.

    Car__Update --> Used to update a car.

    Car__Delete --> Used to delete a car. """
    class Meta:
        abstract = True
```

```python
# File: schema/__init__.py (assuming this is where the main_schema object lives)
import graphene
from apps.car.api.schema import Query as CarQueries
from apps.car.api.schema import Mutation as CarMutations


class Query(CarQueries):
    """ This class should sub-class query classes from all apps to include them
    in the schema."""
    pass


class Mutation(CarMutations):
    """ This class should sub-class mutation classes from all apps to include them
    in the schema."""
    pass


main_schema = graphene.Schema(query=Query, mutation=Mutation)
```

## For more information

Each of the main classes / functions in this module are well documented, so
have a look at the comments on each to get a better understanding of their
purpose.
