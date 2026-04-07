from datetime import date

def update_member_status(member):
    today = date.today()
    end_date = member['end_date']

    if end_date < today:
        return "Expired"
    elif (end_date - today).days <= 3:
        return "Expiring Soon"
    else:
        return "Active"
