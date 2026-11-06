CREATE TABLE bar (
	b_id INT PRIMARYKEY,
	name VARCHAR(50) NOTNULL,
	city VARCHAR(50)
);
CREATE TABLE serves (
	b_id INT REFERENCESbar(b_id),
	c_id INT REFERENCEScocktail(c_id),
price DECIMAL(5,2),
PRIMARY KEY(b_id, c_id)
);
