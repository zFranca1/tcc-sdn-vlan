from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://docker:docker@localhost:5431/sdn'
db = SQLAlchemy(app)

class Vlan(db.Model):
    __tablename__ = 'vlan_ports'
    id = db.Column(db.Integer, primary_key=True)
    vlan_id = db.Column(db.Integer, nullable=False)
    port_number = db.Column(db.Integer, nullable=False)

    def __init__(self, vlan_id, port_number):
        self.vlan_id = vlan_id
        self.port_number = port_number

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        vlan_id = request.form['vlan_id']
        port_number = request.form['port_number']

        existing_vlan = Vlan.query.filter_by(port_number=port_number).first()
        if existing_vlan:
            return f"A porta {port_number} já possui uma VLAN associada."

        vlan = Vlan(vlan_id=vlan_id, port_number=port_number)
        db.session.add(vlan)
        db.session.commit()

        return redirect(url_for('index'))

    vlans = Vlan.query.all()
    return render_template('index.html', vlans=vlans)

# Rota para editar uma VLAN
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    vlan = Vlan.query.get(id)
    if request.method == 'POST':
        vlan_id = request.form['vlan_id']
        port_number = request.form['port_number']

        existing_vlan = Vlan.query.filter_by(port_number=port_number).first()
        if existing_vlan and existing_vlan.id != id:
            return f"A porta {port_number} já possui uma VLAN associada."

        vlan.vlan_id = vlan_id
        vlan.port_number = port_number
        
        db.session.commit()
        return redirect(url_for('index'))
    
    return render_template('edit.html', vlan=vlan)

# Rota para deletar uma VLAN
@app.route('/delete/<int:id>')
def delete(id):
    vlan = Vlan.query.get(id)
    db.session.delete(vlan)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
