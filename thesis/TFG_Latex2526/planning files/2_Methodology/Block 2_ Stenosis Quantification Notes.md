**Stenosis Quantification Methodology**

Aquest bloc té com a objectiu transformar la informació geomètrica extreta en el Bloc 1 en mètriques de rellevància clínica. S'implementa una pipeline automàtica per a la quantificació de l'estenosi basada en l'àrea seccional 3D, utilitzant mètodes de referència espacial (sliding window) i distància geodèsica per garantir la fidelitat anatòmica. 

## **1\. Area Computation (VMTK Sectional Extraction)**

Aquí va la part de vmtkCenterlineSections per obtindre la area seccional en cada punt de l’arbre coronari global.

Es realitza l'extracció de l'àrea transversal del lumen. A diferència del càlcul basat en el radi (MISR), l'àrea transversal capta la reducció real de la secció vascular en plaques excèntriques. S'utilitza l'algorisme de seccionament ortogonal de VMTK sobre la malla superficial suavitzada del Bloc 1\.

En les artèries coronàries, la placa no creix sempre de forma concèntrica (com un anell perfecte). Sovint és excèntrica (creix més cap a un costat que cap a l'altre).

* **El problema del Diàmetre:** El radi que està donant VMTK ara mateix (MISR \- Maximum Inscribed Sphere Radius) és el radi de l'esfera més gran que cap dins del vas. Si el vas té una forma elíptica a causa d'una placa irregular, el diàmetre només captarà la dimensió més estreta, ignorant que potser hi ha espai lateral per on circula la sang.  
    
* **L'avantatge de l'Àrea:** L'àrea transversal capta la reducció real de la "canonada", independentment de si la forma és circular, ovalada o totalment irregular. Clínicament, això correlaciona molt millor amb la caiguda de pressió i el flux sanguini. La area ajuda a veure la caiguda de pressió del flux de la sang és líquid. 

## **2\. Branch Path Processing & Mapping**

El bucle que llegeix els *branch dataframes* que hem creat anteriorment i fa el mapping d'àrea mitjançant **KDTree**.

Per a una avaluació segmentària, l'arbre coronari es divideix en camins individuals des de l'ostium fins a cada endpoint. Atès que el mostreig de les branques pot diferir de la centerline global, s'utilitza una estructura de dades **KDTree** per mapejar espacialment els valors d'àrea calculats a cada node de les branques.

## **3\. Geodesic Distance & Reference Values**

Càlcul de gd (cumsum de distàncies euclidianes) i cerca de Area\_prox i Area\_dist amb la finestra de 10mm.

Es calcula la distància geodèsica al llarg del vas. Per determinar la severitat d'una lesió, s'aplica el **mètode "Value"** amb una finestra de referència (W) de 10 mm.

* **Criteri d'exclusió:** Els punts situats a menys de 10 mm dels extrems es marquen com NaN, ja que no disposen de context proximal o distal suficient per a un càlcul de referència fiable.

## **4\. Stenosis Quantification & Data Aggregation**

Càlcul de pct\_AS i la unificació final (drop\_duplicates amb criteri del màxim).

S'aplica la fórmula de l'estenosi per àrea (%AS). Finalment, es realitza una unificació de dades (grups per punts a prop) per obtenir un dataset global del pacient.

* **Criteri Clínic del Valor Màxim:** En zones d'encavallament (com el Tronc Comú), es prioritza el valor de %AS més sever detectat. Aquesta decisió de disseny garanteix un sistema de suport a la decisió conservador que no subestima les lesions en punts de bifurcació.

