"""Small illustrative fixtures authored for the public demo, unrelated to source rows."""
import pandas as pd

def demo_tables():
    support = []
    finance = []
    for i in range(1, 11):
        support.append({'Ticket ID':f'RF-{9000+i}', 'Agent':f'Demo Agency {i}', 'Route':'DEL-BOM',
                        'Refund Amount (INR)':1000*i, 'Request Date':f'{i:02d}-06-2026',
                        'Last Updated':'20-06-2026', 'Status':'Closed' if i<8 else 'Working',
                        'Handled By':'Demo Support', 'Channel':'Email', 'Notes':'Illustrative generated record'})
        if i not in [3,4]:
            finance.append({'Ref No':f'RF-{9000+i}', 'Agent Name':f'Demo Agency {i}', 'Sector':'DEL-BOM',
                            'Amount Paid (INR)':1000*i if i != 2 else None,
                            'Deduction (INR)':0, 'Received On':f'{i+1:02d}-06-2026',
                            'Processed On':'19-06-2026' if i!=2 else None,
                            'Payout Status':'Refund Done' if i!=2 else 'Pending Payout',
                            'Approved By':'Demo Finance', 'Remarks':'Illustrative generated record'})
    support.append(dict(support[0]))
    support.append(dict(support[5], **{'Refund Amount (INR)':5500}))
    finance[4]['Amount Paid (INR)'] = 6500
    escalations = [
        {'Escalation ID':'DEMO-1','Raised On':'20-06-2026','Related Ticket / Ref':'RF-9003',
         'Raised By':'Agent','Agent / Team':'Demo Agency 3','Channel':'Email',
         'Complaint':'Ticket shows closed, Finance has no record of this refund','Status':'Open','Resolved On':None,'Days Open':10},
        {'Escalation ID':'DEMO-2','Raised On':'22-06-2026','Related Ticket / Ref':'no ref',
         'Raised By':'Agent','Agent / Team':'Unverified Demo Agency','Channel':'WhatsApp',
         'Complaint':'WhatsApp request ignored entirely. Never got a ticket number','Status':'Open','Resolved On':None,'Days Open':8},
    ]
    return {'Support_Tracker':pd.DataFrame(support),'Finance_Tracker':pd.DataFrame(finance),'Escalations':pd.DataFrame(escalations)}
