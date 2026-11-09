# Resultados experimentales

Generado por `experimentos/ejecutar_experimentos.py`.

Escenario base: {'cantidad_estantes': 24, 'cantidad_pasillos': 7, 'cantidad_productos': 200, 'localizacion': 'DISTRIBUIDA', 'cantidad_pedidos': 40, 'max_productos_por_pedido': 5, 'wave_max_pedidos': 4, 'wave_max_productos': 20, 'cantidad_pickers': 4}

### Tamaño del warehouse (estantes)

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 294 | 211 | 200 | 40 | 13 | Orden | 1862 | 1088 | 2709 | 11151 | 46.55 | 674 | 88 |
| 6 | 294 | 211 | 200 | 40 | 13 | Cercanía | 871 | 826 | 2356 | 4672 | 19.53 | 437 | 57 |
| 12 | 522 | 356 | 200 | 40 | 13 | Orden | 3320 | 1817 | 4618 | 27504 | 116.27 | 1114 | 99 |
| 12 | 522 | 356 | 200 | 40 | 13 | Cercanía | 1554 | 1377 | 4461 | 11499 | 48.85 | 718 | 55 |
| 24 | 990 | 680 | 200 | 40 | 13 | Orden | 2395 | 1563 | 7636 | 22632 | 104.13 | 874 | 18 |
| 24 | 990 | 680 | 200 | 40 | 13 | Cercanía | 1565 | 1376 | 7248 | 14707 | 71.34 | 708 | 23 |

### Cantidad de pedidos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 962 | 652 | 200 | 10 | 3 | Orden | 458 | 276 | 1103 | 3924 | 17.56 | 237 | 4 |
| 10 | 962 | 652 | 200 | 10 | 3 | Cercanía | 300 | 261 | 1094 | 2578 | 12.27 | 194 | 15 |
| 20 | 962 | 652 | 200 | 20 | 6 | Orden | 1034 | 587 | 2741 | 9429 | 42.48 | 484 | 25 |
| 20 | 962 | 652 | 200 | 20 | 6 | Cercanía | 560 | 510 | 2393 | 4788 | 23.61 | 320 | 9 |
| 40 | 962 | 652 | 200 | 40 | 13 | Orden | 2435 | 1683 | 7269 | 24428 | 109.86 | 869 | 30 |
| 40 | 962 | 652 | 200 | 40 | 13 | Cercanía | 1607 | 1483 | 7184 | 16139 | 73.91 | 679 | 21 |

### Cantidad de productos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 25 | 962 | 652 | 25 | 40 | 13 | Orden | 2394 | 2080 | 8397 | 28025 | 135.41 | 845 | 66 |
| 25 | 962 | 652 | 25 | 40 | 13 | Cercanía | 1805 | 1714 | 8102 | 18882 | 84.39 | 717 | 49 |
| 50 | 962 | 652 | 50 | 40 | 13 | Orden | 2574 | 2138 | 8122 | 27736 | 131.41 | 911 | 34 |
| 50 | 962 | 652 | 50 | 40 | 13 | Cercanía | 2004 | 1826 | 8136 | 19843 | 102.36 | 751 | 12 |
| 100 | 962 | 652 | 100 | 40 | 13 | Orden | 3909 | 2796 | 8368 | 48109 | 238.10 | 1257 | 28 |
| 100 | 962 | 652 | 100 | 40 | 13 | Cercanía | 2281 | 2070 | 8134 | 23163 | 110.49 | 838 | 42 |

### Localización de los productos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CERCA_DESPACHO | 962 | 652 | 200 | 40 | 13 | Orden | 3563 | 2347 | 8268 | 44532 | 213.99 | 1236 | 92 |
| CERCA_DESPACHO | 962 | 652 | 200 | 40 | 13 | Cercanía | 1919 | 1741 | 7965 | 19791 | 89.58 | 781 | 46 |
| POR_RACK | 962 | 652 | 200 | 40 | 12 | Orden | 3210 | 1532 | 7590 | 39679 | 201.18 | 1024 | 40 |
| POR_RACK | 962 | 652 | 200 | 40 | 12 | Cercanía | 1449 | 1263 | 6819 | 15777 | 73.62 | 637 | 39 |
| DISTRIBUIDA | 962 | 652 | 200 | 40 | 13 | Orden | 2435 | 1683 | 7269 | 24428 | 132.39 | 869 | 30 |
| DISTRIBUIDA | 962 | 652 | 200 | 40 | 13 | Cercanía | 1607 | 1483 | 7184 | 16139 | 74.52 | 679 | 21 |

### Cantidad de pasillos

| Valor | Celdas | Nodos | Productos | Pedidos | Waves | Estrategia | Distancia | Nodos visitados | Nodos explorados | Nodos expandidos | Rutas (ms) | Turnos | Esperas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 1010 | 711 | 200 | 40 | 13 | Orden | 3366 | 2373 | 7692 | 19901 | 85.04 | 1130 | 69 |
| 3 | 1010 | 711 | 200 | 40 | 13 | Cercanía | 2685 | 2333 | 7353 | 15822 | 74.30 | 938 | 60 |
| 5 | 954 | 644 | 200 | 40 | 12 | Orden | 2468 | 1651 | 6732 | 21038 | 95.31 | 933 | 44 |
| 5 | 954 | 644 | 200 | 40 | 12 | Cercanía | 1520 | 1396 | 5927 | 12667 | 56.99 | 658 | 51 |
| 7 | 962 | 652 | 200 | 40 | 13 | Orden | 2435 | 1683 | 7269 | 24428 | 116.75 | 869 | 30 |
| 7 | 962 | 652 | 200 | 40 | 13 | Cercanía | 1607 | 1483 | 7184 | 16139 | 75.89 | 679 | 21 |

### Tiempo de cada etapa (estrategia Cercanía)

| Serie | Valor | Celdas | Nodos | Aristas | Dígrafo (ms) | Kosaraju (ms) | Matriz (ms) | Pares matriz | Waves (ms) | Candidatos evaluados |
|---|---|---|---|---|---|---|---|---|---|---|
| tamano | 6 | 294 | 211 | 552 | 1.83 | 0.33 | 43.6 | 5184 | 11.97 | 383 |
| tamano | 12 | 522 | 356 | 900 | 3.30 | 0.55 | 165.3 | 20736 | 13.15 | 402 |
| tamano | 24 | 990 | 680 | 1754 | 5.86 | 1.17 | 513.7 | 40000 | 16.50 | 423 |
| pedidos | 10 | 962 | 652 | 1678 | 5.34 | 1.03 | 428.0 | 40000 | 3.54 | 30 |
| pedidos | 20 | 962 | 652 | 1678 | 5.41 | 1.01 | 577.8 | 40000 | 6.21 | 115 |
| pedidos | 40 | 962 | 652 | 1678 | 5.59 | 1.02 | 455.6 | 40000 | 13.42 | 404 |
| productos | 25 | 962 | 652 | 1678 | 5.24 | 1.03 | 54.8 | 625 | 9.17 | 405 |
| productos | 50 | 962 | 652 | 1678 | 5.15 | 1.06 | 107.0 | 2500 | 9.88 | 365 |
| productos | 100 | 962 | 652 | 1678 | 5.62 | 1.03 | 290.2 | 10000 | 15.17 | 367 |
| localizacion | CERCA_DESPACHO | 962 | 652 | 1678 | 5.64 | 1.03 | 434.7 | 40000 | 13.87 | 389 |
| localizacion | POR_RACK | 962 | 652 | 1678 | 5.83 | 1.03 | 457.8 | 40000 | 13.93 | 357 |
| localizacion | DISTRIBUIDA | 962 | 652 | 1678 | 7.39 | 1.14 | 468.1 | 40000 | 14.69 | 404 |
| pasillos | 3 | 1010 | 711 | 1720 | 7.53 | 1.57 | 463.3 | 40000 | 14.54 | 392 |
| pasillos | 5 | 954 | 644 | 1602 | 5.55 | 0.98 | 438.7 | 40000 | 12.60 | 381 |
| pasillos | 7 | 962 | 652 | 1678 | 5.73 | 1.03 | 436.2 | 40000 | 18.18 | 404 |

### Estrategias de armado de waves (recorrido con Cercanía)

| Escenario | Armado | Waves | Pedidos/wave | Pasillos/wave | Prioridad 1.ª wave | Distancia | Turnos | Armado (ms) | Candidatos |
|---|---|---|---|---|---|---|---|---|---|
| pedidos=20 | Cercanía | 6 | 3.33 | 4.17 | 2.75 | 560 | 320 | 5.11 | 115 |
| pedidos=20 | Por pasillo | 7 | 2.86 | 4.0 | 3.33 | 631 | 340 | 1.98 | 98 |
| pedidos=20 | Solo prioridad | 6 | 3.33 | 5.83 | 3.67 | 686 | 385 | 1.53 | 100 |
| pedidos=40 | Cercanía | 13 | 3.08 | 4.54 | 2.75 | 1607 | 679 | 11.68 | 404 |
| pedidos=40 | Por pasillo | 13 | 3.08 | 4.46 | 3.33 | 1527 | 697 | 5.82 | 358 |
| pedidos=40 | Solo prioridad | 13 | 3.08 | 5.77 | 3.67 | 1844 | 796 | 2.77 | 376 |
| pedidos=80 | Cercanía | 27 | 2.96 | 4.04 | 2.25 | 2750 | 1193 | 37.57 | 1447 |
| pedidos=80 | Por pasillo | 25 | 3.2 | 4.28 | 3.33 | 2893 | 1278 | 12.46 | 1375 |
| pedidos=80 | Solo prioridad | 25 | 3.2 | 6.08 | 3.67 | 3592 | 1457 | 9.41 | 1413 |
| pedidos=160 | Cercanía | 52 | 3.08 | 3.94 | 2.5 | 5604 | 2318 | 146.67 | 5752 |
| pedidos=160 | Por pasillo | 49 | 3.27 | 3.8 | 3.33 | 5691 | 2378 | 47.24 | 5446 |
| pedidos=160 | Solo prioridad | 52 | 3.08 | 6.08 | 3.67 | 7790 | 2974 | 32.96 | 6408 |
| localizacion=CERCA_DESPACHO | Cercanía | 13 | 3.08 | 6.38 | 2.25 | 1919 | 781 | 10.49 | 389 |
| localizacion=CERCA_DESPACHO | Por pasillo | 13 | 3.08 | 6.31 | 2.25 | 2010 | 858 | 4.07 | 382 |
| localizacion=CERCA_DESPACHO | Solo prioridad | 13 | 3.08 | 8.23 | 3.67 | 2261 | 846 | 2.74 | 376 |
| localizacion=POR_RACK | Cercanía | 12 | 3.33 | 4.67 | 3.33 | 1449 | 637 | 9.53 | 357 |
| localizacion=POR_RACK | Por pasillo | 13 | 3.08 | 4.08 | 3.33 | 1341 | 638 | 3.87 | 359 |
| localizacion=POR_RACK | Solo prioridad | 13 | 3.08 | 7.08 | 3.67 | 1893 | 754 | 2.73 | 376 |

![Armado de waves](armado.png)

### Validación de escenarios inválidos y trampas topológicas (Secciones 3, 16 y 23.6)

| Caso de prueba | Regla del enunciado verificada | Resultado | Tiempo (ms) | Mensaje de error capturado (`ValueError`) |
|---|---|---|---|---|
| `1_Racks_Solapados` | Sección 3.1 y 16: Dos elementos no pueden solaparse | **RECHAZADO OK** | 0.153 | Elementos superpuestos: R_SOLAPADO |
| `2_Rack_Sin_Lado_2` | Sección 3.2 y 16: Todo rack debe tener un lado igual a 2 | **RECHAZADO OK** | 0.142 | Un lado del rack debe medir 2. |
| `3_Puerta_Fuera_Del_Borde` | Sección 3.3 y 16: Las puertas deben ubicarse sobre el borde | **RECHAZADO OK** | 0.155 | Puerta fuera del borde. |
| `4_Producto_Fuera_De_Rack` | Sección 4 y 16: Todo producto debe estar ubicado dentro de un rack | **RECHAZADO OK** | 0.250 | Producto fuera de su rack. |
| `5_Picker_En_Obstaculo` | Sección 3.6: La posición inicial del picker debe ser una celda de pasillo | **RECHAZADO OK** | 0.297 | Picker inválido. |
| `6_Trampa_Topologica_Sin_Retorno` | Sección 8 y 16 (Kosaraju SCC): Sin camino de regreso a Zona de Despacho | **RECHAZADO OK** | 2.133 | Escenario inválido por desconexión topológica (sin camino de ida y vuelta para picker):  |
