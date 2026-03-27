import json

path = r'C:\Users\Ryzen 5 5600g\Desktop\fc_companion\state.json'
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

team_id = data['club']['team_id']
print('Team ID:', team_id)

comp = data['club']['season_stats']['competition_id']
print('Comp ID:', comp)

standings = [t for t in data['standings'] if t['competition_id'] == comp]

def sort_key(x):
    total = x.get('total', {})
    wins = total.get('wins', 0)
    draws = total.get('draws', 0)
    calc_points = (wins * 3) + draws
    mem_points = total.get('points', 0)
    
    # Let's print what points we are using
    points = mem_points if mem_points > 0 else calc_points
    
    gd = total.get('goals_for', 0) - total.get('goals_against', 0)
    gf = total.get('goals_for', 0)
    
    return (points, gd, gf)

standings.sort(key=sort_key, reverse=True)

print('Standings:')
for i, t in enumerate(standings[:10]):
    total = t.get('total', {})
    calc_points = (total.get('wins', 0) * 3) + total.get('draws', 0)
    print(f"{i+1}. {t.get('team_name')} - MemPts: {total.get('points')} CalcPts: {calc_points} (W:{total.get('wins')} D:{total.get('draws')} L:{total.get('losses')}) GD: {total.get('goals_for', 0) - total.get('goals_against', 0)} GF: {total.get('goals_for', 0)}")

my_pos = next((i+1 for i, t in enumerate(standings) if t['team_id'] == team_id), -1)
print('My team pos:', my_pos)
