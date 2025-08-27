def is_employee(user):
    return user.is_authenticated and user.groups.filter(name="employees").exists()
