# Instrumentos de evaluación clínica (C2.A4 y C2.A5)

Estos archivos los completa el médico colaborador. No hace falta que 
ejecute nada: solo llenar los CSV y devolverlos. El cálculo lo hace 
`python scripts/evaluar.py rubrica`.

## 1. `rubrica_clinica.csv` — calidad clínica de cada respuesta (C2.A4)

Para cada uno de los 20 casos clínicos, califique la respuesta del sistema 
en la columna `calificacion` con uno de estos cuatro valores:

| Valor | Significado |
|---|---|
| Muy bueno | El nivel de urgencia es correcto y las acciones recomendadas son 
adecuadas y seguras para una posta rural. |
| Bueno | El nivel es correcto, con recomendaciones incompletas o poco 
específicas que no comprometen la seguridad. |
| Regular | El nivel es discutible (sub o sobrevaloración leve) o faltan 
elementos importantes de manejo. |
| Malo | El nivel es incorrecto o la respuesta contiene indicaciones 
peligrosas. |

La columna `nivel_sistema` muestra lo que respondió el sistema y 
`nivel_esperado` lo que se considera correcto según las NNAC; el médico 
puede corregir el nivel esperado en `comentario` si no está de acuerdo.

Criterio de aceptación del Componente 2: **al menos 80 % de los casos en 
Bueno o Muy bueno**.

## 2. `encuesta_sus.csv` — usabilidad percibida (C2.A5)

Responder los 10 ítems con la escala de 1 (muy en desacuerdo) a 5 (muy de 
acuerdo). El puntaje se calcula en la escala estándar 0-100 y el criterio 
de aceptación es **70 puntos o más**.

## 3. Cómo devolverlo

Copiar los dos CSV en `evaluacion/instrumentos/` del repositorio y ejecutar:

```
python scripts/evaluar.py rubrica --run <archivo-de-corrida.json>
```

Eso genera `evaluacion/informes/informe_clinico.md` con el porcentaje de 
casos aceptables, el puntaje SUS y la concordancia con el veredicto 
automático del sistema.
