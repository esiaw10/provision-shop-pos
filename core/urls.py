from core import views

path("admin/stores/", views.manage_stores, name="manage_stores"),
path("admin/stores/add/", views.add_store, name="add_store"),
path("admin/stores/<int:store_id>/edit/", views.edit_store, name="edit_store"),
path("admin/stores/<int:store_id>/delete/",
     views.delete_store, name="delete_store"),
path("admin/stores/<int:store_id>/toggle/",
     views.toggle_store, name="toggle_store"),
