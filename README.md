Copyright 2022 Häme University of Applied Sciences
Authors: Olli Niemitalo, Genrikh Ekkerman

This work is licensed under the MIT license and is distributed without any warranty.

The following folders have their separate copyright:
/nlohmann
/simcpp



# Planning document for Genrikh's and Olli's work during the summer 2022

## Init
Create a list of orders with start date

## For each day D in simulation
1.	select the orders that are visible for organizer at D
2.	prioritize based on how many days are left to full-fill order (i.e., if some order has been pushed from previous days and is now on the last day of service level agreement)
3.	route the trucks for today and set the routed orders to complete
4.	prepare next day
    1.	grow load on grey containers: estimate the growth of the grey ones so that days between 0 and 100 percent full is normally distributed and we can approximate growth in between just linearly. The mean and std might be different for each container though (ones closer to bigger city centers are emptied more often than ones further away). Maybe simplify first so that just set a constant interval for each grey box and grow linearly between emptying and next order.
        *	when empty for each container with its own mean and std, pick the next emptying date and then grow linearly in between
        *	14-21 days to full. 
	1.	update the status on trucks (load after the workday if not emptied in the end, location – these might be later left also somewhere else than deposit)

## Research questions
1.	Compare two cases: A) grey containers added when full versus B) grey containers added when the P percent full. In B, the >95% full containers are prioritized over containers between P and 95% full, but if routing allows efficient visit to these lower filled containers, they are emptied too. Then test with different values of P ranging between like 65 to 90.
(A).	Rules of efficient visit
    1.	Time offset <= T. And optimize for P and T
    2.	"there's slack to be filled in the day routine" i.e. a lesser priority container is picked if it is closer in spacial distance that the next closest placed order AND the next closest placed order can still be completed today or does allow scheduling for next day.
2.	How much ahead does it make sense to organize the routes?
3.	How much more routing efficiency can be gained with longer fulfilling time (SLA)?

## First case 9.8.2022 plan
List of municipalities to include: Hämeenlinna, Hattula, Janakkala, Hausjärvi, Riihimäki, Loppi, Tammela, Forssa, Jokioinen
http://kuntakartta.org
List of grey cites for glass from rinkiin.fi
https://rinkiin.fi/tietoa-ringista/suomen-kerayslasiyhdistys/lasipakkausten-terminaalit/
https://rinkiin.fi/kotitalouksille/rinki-ekopisteet/

## Notes
1.	Daily driving times: https://www.tyosuojelu.fi/web/en/employment-relationship/driving-times-rest-periods/rules	 
