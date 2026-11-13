SELECT c_id,
	COUNT(*) AS cocktails,
	AVG(price) AS avg_price
FROM serves
GROUP	BY c_id
HAVING COUNT(*) >= 2
ORDER BY avg_price DESC;