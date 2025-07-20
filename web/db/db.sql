CREATE TABLE public.vlan_ports (
	id serial4 NOT NULL,
	vlan_id int4 NOT NULL,
	port_number int4 NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT vlan_ports_pkey PRIMARY KEY (id)
);
