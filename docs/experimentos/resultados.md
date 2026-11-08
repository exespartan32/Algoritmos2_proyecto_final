# Resultados experimentales

Generado por `experimentos/ejecutar_experimentos.py`.

Escenario base: {'cantidad_estantes': 24, 'cantidad_pasillos': 7, 'cantidad_productos': 200, 'localizacion': 'DISTRIBUIDA', 'cantidad_pedidos': 40, 'max_productos_por_pedido': 5, 'wave_max_pedidos': 4, 'wave_max_productos': 20, 'cantidad_pickers': 4}

### Tamaño del warehouse (estantes)

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 294 | 211 | 200 | 40 | 13 | Orden | 1878 | 1081 | 2709 | 11258 | 50.51 | 699 | 116 |
| 6 | 294 | 211 | 200 | 40 | 13 | Cercanía | 871 | 826 | 2356 | 4672 | 19.50 | 433 | 56 |
| 12 | 522 | 356 | 200 | 40 | 13 | Orden | 3322 | 1819 | 4618 | 27517 | 124.28 | 1098 | 97 |
| 12 | 522 | 356 | 200 | 40 | 13 | Cercanía | 1554 | 1377 | 4461 | 11499 | 49.54 | 714 | 55 |
| 24 | 990 | 680 | 200 | 40 | 13 | Orden | 2395 | 1563 | 7636 | 22632 | 123.94 | 870 | 18 |
| 24 | 990 | 680 | 200 | 40 | 13 | Cercanía | 1565 | 1376 | 7248 | 14707 | 67.42 | 704 | 23 |

### Cantidad de pedidos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 962 | 652 | 200 | 10 | 3 | Orden | 458 | 276 | 1103 | 3924 | 17.58 | 236 | 4 |
| 10 | 962 | 652 | 200 | 10 | 3 | Cercanía | 300 | 261 | 1094 | 2578 | 11.67 | 193 | 15 |
| 20 | 962 | 652 | 200 | 20 | 6 | Orden | 1034 | 587 | 2741 | 9429 | 45.61 | 483 | 26 |
| 20 | 962 | 652 | 200 | 20 | 6 | Cercanía | 560 | 510 | 2393 | 4788 | 22.07 | 318 | 9 |
| 40 | 962 | 652 | 200 | 40 | 13 | Orden | 2435 | 1683 | 7269 | 24428 | 123.23 | 865 | 30 |
| 40 | 962 | 652 | 200 | 40 | 13 | Cercanía | 1607 | 1483 | 7184 | 16139 | 79.29 | 675 | 21 |

### Cantidad de productos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 25 | 962 | 652 | 25 | 40 | 13 | Orden | 2394 | 2080 | 8397 | 28025 | 134.92 | 842 | 71 |
| 25 | 962 | 652 | 25 | 40 | 13 | Cercanía | 1805 | 1714 | 8102 | 18882 | 87.13 | 714 | 49 |
| 50 | 962 | 652 | 50 | 40 | 13 | Orden | 2574 | 2138 | 8122 | 27736 | 123.31 | 907 | 31 |
| 50 | 962 | 652 | 50 | 40 | 13 | Cercanía | 2004 | 1826 | 8136 | 19843 | 90.04 | 748 | 11 |
| 100 | 962 | 652 | 100 | 40 | 13 | Orden | 3909 | 2796 | 8368 | 48109 | 249.82 | 1252 | 30 |
| 100 | 962 | 652 | 100 | 40 | 13 | Cercanía | 2281 | 2070 | 8134 | 23163 | 108.48 | 830 | 50 |

### Localización de los productos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CERCA_DESPACHO | 962 | 652 | 200 | 40 | 13 | Orden | 3563 | 2347 | 8268 | 44532 | 204.64 | 1217 | 84 |
| CERCA_DESPACHO | 962 | 652 | 200 | 40 | 13 | Cercanía | 1919 | 1741 | 7965 | 19791 | 92.94 | 777 | 46 |
| POR_RACK | 962 | 652 | 200 | 40 | 12 | Orden | 3210 | 1532 | 7590 | 39679 | 184.23 | 1021 | 40 |
| POR_RACK | 962 | 652 | 200 | 40 | 12 | Cercanía | 1449 | 1263 | 6819 | 15777 | 72.23 | 633 | 36 |
| DISTRIBUIDA | 962 | 652 | 200 | 40 | 13 | Orden | 2435 | 1683 | 7269 | 24428 | 109.43 | 865 | 30 |
| DISTRIBUIDA | 962 | 652 | 200 | 40 | 13 | Cercanía | 1607 | 1483 | 7184 | 16139 | 72.68 | 675 | 21 |

### Cantidad de pasillos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 1010 | 711 | 200 | 40 | 13 | Orden | 3366 | 2373 | 7692 | 19901 | 83.12 | 1124 | 85 |
| 3 | 1010 | 711 | 200 | 40 | 13 | Cercanía | 2685 | 2333 | 7353 | 15822 | 66.11 | 935 | 61 |
| 5 | 954 | 644 | 200 | 40 | 12 | Orden | 2468 | 1651 | 6732 | 21038 | 115.78 | 938 | 47 |
| 5 | 954 | 644 | 200 | 40 | 12 | Cercanía | 1520 | 1396 | 5927 | 12667 | 94.33 | 664 | 47 |
| 7 | 962 | 652 | 200 | 40 | 13 | Orden | 2435 | 1683 | 7269 | 24428 | 150.66 | 865 | 30 |
| 7 | 962 | 652 | 200 | 40 | 13 | Cercanía | 1607 | 1483 | 7184 | 16139 | 94.62 | 675 | 21 |

### Tiempo de cada etapa (estrategia Cercanía)

| Serie | Valor | Celdas | Nodos | Aristas | Dígrafo (ms) | Kosaraju (ms) | Matriz (ms) | Pares matriz | Waves (ms) | Candidatos evaluados |
|---|---|---|---|---|---|---|---|---|---|---|
| tamano | 6 | 294 | 211 | 552 | 2.31 | 0.47 | 49.4 | 5184 | 12.66 | 383 |
| tamano | 12 | 522 | 356 | 900 | 3.21 | 0.56 | 157.6 | 20736 | 13.49 | 402 |
| tamano | 24 | 990 | 680 | 1754 | 6.18 | 1.12 | 439.4 | 40000 | 15.32 | 423 |
| pedidos | 10 | 962 | 652 | 1678 | 5.60 | 1.03 | 435.5 | 40000 | 3.39 | 30 |
| pedidos | 20 | 962 | 652 | 1678 | 5.55 | 1.04 | 425.3 | 40000 | 5.92 | 115 |
| pedidos | 40 | 962 | 652 | 1678 | 5.70 | 1.06 | 441.9 | 40000 | 14.37 | 404 |
| productos | 25 | 962 | 652 | 1678 | 6.18 | 1.06 | 51.6 | 625 | 9.22 | 405 |
| productos | 50 | 962 | 652 | 1678 | 5.29 | 1.04 | 103.0 | 2500 | 10.12 | 365 |
| productos | 100 | 962 | 652 | 1678 | 5.42 | 1.04 | 203.7 | 10000 | 10.97 | 367 |
| localizacion | CERCA_DESPACHO | 962 | 652 | 1678 | 6.14 | 1.06 | 454.3 | 40000 | 14.07 | 389 |
| localizacion | POR_RACK | 962 | 652 | 1678 | 5.66 | 1.03 | 421.1 | 40000 | 11.91 | 357 |
| localizacion | DISTRIBUIDA | 962 | 652 | 1678 | 5.57 | 1.08 | 423.0 | 40000 | 14.89 | 404 |
| pasillos | 3 | 1010 | 711 | 1720 | 5.55 | 1.03 | 416.6 | 40000 | 14.48 | 392 |
| pasillos | 5 | 954 | 644 | 1602 | 5.38 | 0.99 | 461.7 | 40000 | 14.54 | 381 |
| pasillos | 7 | 962 | 652 | 1678 | 11.23 | 1.58 | 619.5 | 40000 | 21.87 | 404 |

### Estrategias de armado de waves (recorrido con Cercanía)

| Escenario | Armado | Waves | Pedidos/wave | Pasillos/wave | Prioridad 1.ª wave | Distancia | Turnos | Armado (ms) | Candidatos |
|---|---|---|---|---|---|---|---|---|---|
| pedidos=20 | Cercanía | 6 | 3.33 | 4.17 | 2.75 | 560 | 318 | 5.67 | 115 |
| pedidos=20 | Por pasillo | 7 | 2.86 | 4.0 | 3.33 | 631 | 339 | 1.64 | 98 |
| pedidos=20 | Solo prioridad | 6 | 3.33 | 5.83 | 3.67 | 686 | 383 | 1.13 | 100 |
| pedidos=40 | Cercanía | 13 | 3.08 | 4.54 | 2.75 | 1607 | 675 | 17.64 | 404 |
| pedidos=40 | Por pasillo | 13 | 3.08 | 4.46 | 3.33 | 1527 | 689 | 5.03 | 358 |
| pedidos=40 | Solo prioridad | 13 | 3.08 | 5.77 | 3.67 | 1844 | 793 | 2.95 | 376 |
| pedidos=80 | Cercanía | 27 | 2.96 | 4.04 | 2.25 | 2750 | 1184 | 49.74 | 1447 |
| pedidos=80 | Por pasillo | 25 | 3.2 | 4.28 | 3.33 | 2893 | 1245 | 19.20 | 1375 |
| pedidos=80 | Solo prioridad | 25 | 3.2 | 6.08 | 3.67 | 3592 | 1454 | 10.81 | 1413 |
| pedidos=160 | Cercanía | 52 | 3.08 | 3.94 | 2.5 | 5608 | 2301 | 191.13 | 5752 |
| pedidos=160 | Por pasillo | 49 | 3.27 | 3.8 | 3.33 | 5682 | 2362 | 47.88 | 5446 |
| pedidos=160 | Solo prioridad | 52 | 3.08 | 6.08 | 3.67 | 7774 | 2940 | 37.89 | 6408 |
| localizacion=CERCA_DESPACHO | Cercanía | 13 | 3.08 | 6.38 | 2.25 | 1919 | 777 | 11.56 | 389 |
| localizacion=CERCA_DESPACHO | Por pasillo | 13 | 3.08 | 6.31 | 2.25 | 2010 | 853 | 5.47 | 382 |
| localizacion=CERCA_DESPACHO | Solo prioridad | 13 | 3.08 | 8.23 | 3.67 | 2261 | 865 | 2.95 | 376 |
| localizacion=POR_RACK | Cercanía | 12 | 3.33 | 4.67 | 3.33 | 1449 | 633 | 13.47 | 357 |
| localizacion=POR_RACK | Por pasillo | 13 | 3.08 | 4.08 | 3.33 | 1341 | 634 | 5.99 | 359 |
| localizacion=POR_RACK | Solo prioridad | 13 | 3.08 | 7.08 | 3.67 | 1893 | 750 | 4.88 | 376 |

![Armado de waves](armado.png)
