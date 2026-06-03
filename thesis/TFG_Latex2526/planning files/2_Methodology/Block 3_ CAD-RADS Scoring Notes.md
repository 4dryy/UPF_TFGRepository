**Labeling Usage**  
L'ús de les dades de *labeling* no només millorarà la fiabilitat, sinó que és essencial per complir amb l'estàndard **CAD-RADS 2.0** que hem trobat. Segons el document oficial, la classificació no es basa únicament en un valor global, sinó en la localització anatòmica i la combinació de lesions. 

Si només fessis un max() de tot l'arbre, perdria matisos clínics crítics que defineix el **CAD-RADS 2.0**:

* **Tronc Comú (Left Main \- Segment 5):** Una estenosi del 50-69% al Tronc Comú es classifica directament com a CAD-RADS 4B. Si fos en qualsevol altre segment, seria un CAD-RADS 3\. Sense labels, no podries detectar aquesta severitat especial. Donarem més detall després.   
    
* **Malaltia Multivas:** El CAD-RADS 4B també s'assigna si hi ha 3 vasos amb estenosi obstructiva (70%). Necessites saber a quin vas pertany cada segment per comptar quants vasos estan afectats.

**Bifurcation Issues and Quantification**  
We will handle this later with discussions on how this can be faced. But for the moment we will focus on finishing the block. Indeed, bifurcation geometry and its effect on the stenosis quantification formula is a real important limitation of the workflow because it biases a lot of the results. 

**CAD-RADS Scoring Methodology**

This document covers the detailed methodology that is implemented in the 3rd block of the workflow and the decisions and justifications of each phase. We start this after having quantified the stenosis for each geometrical point.

**ASOCA Segment Labels Data**  
The labeling data that we receive for the ASOCA dataset is stored as a .[nii.gz](http://nii.gz) format.   
This file is a 3D voxel grid (label map), where each voxel stores an integer class ID: 

* 0 usually means background (not artery).  
* 1, 2, 3, … mean different anatomical segments/categories of the coronary tree.

*Ex. voxel(120, 300, 250\) → value 7 \= segment 7*

The file behavior is similar to the one that we use for the input segmentation, the main difference is that instead of storing a binary information for each voxel, now the data stores a multiclass label that identifies the segment. 

## **1\. Ostium Detection Through Labeling**

La metodologia de detecció determinista de l’ostium es basa en el mapatge espacial entre les coordenades físiques de la *centerline* i el volum de *labels* anatòmics de l’ASOCA. 

Mitjançant la matriu **Affine inversa** del fitxer NIfTI, transformem cada punt physical $(x, y, z)$ en índexs de vòxel $(i, j, k)$ per consultar directament a quin segment pertany cada extrem de l'esquelet vascular.   
Aquest procés de mostreig permet etiquetar de forma automàtica els *endpoints* identificats prèviament per la topologia de l'esquelet, assegurant una correspondència exacta entre la geometria del vas i la seva identitat anatòmica.

La selecció de l'ostium segueix una jerarquia de decisions on prima l'anatomia sobre la geometria. El sistema identifica com a ostium aquell punt situat en el **Segment 1** (per a l’RCA) o en el **Segment 5** (per a l’LCA), seguint els estàndards clínics de segmentació coronària definits per l'AHA i el CAD-RADS 2.0. En cas que cap punt es trobi exactament dins del segment objectiu, s'aplica una regla de seguretat fisiològica que selecciona el candidat amb el radi més gran (**Maximum Inscribed Sphere Radius**), garantint que la *centerline* s'orienti sempre de proximal a distal de forma coherent per als càlculs posteriors.

Aquest enfocament és extremadament robust perquè elimina la dependència de puntuacions heurístiques o "scouts" inestables que podien fallar en anatomies tortuoses o amb radiografia complexa. En utilitzar el *Ground Truth* del labeling anatòmic, el sistema guanya certesa clínica i evita esbiaixaments en les fases de quantificació d'àrea i estenosi. Això assegura una integració totalment automatitzada a la *pipeline* que respecta la realitat anatòmica del pacient i facilita la classificació diagnòstica final.

## **2\. Artery Segment Label Mapping & Integration**

L'objectiu és que cada punt de la centerline hereti la identitat del segment on es troba segons els vòxels de l'ASOCA.

1. **Càrrega de dades NIfTI**: Utilitzar la llibreria nibabel per carregar el volum de labels (.nii.gz) i, sobretot, la seva matriu Affine.  
2. **Transformació de Coordenades**:  
   * Per a cada punt $(P\_x, P\_y, P\_z)$ del teu dataframe (que està en mil·límetres), aplicar la inversa de la matriu Affine per obtenir els índexs de vòxel $(i, j, k)$.  
3. **Extracció del Label**: Consultar el valor del volum en aquells índexs i crear una nova columna Label\_ID al teu dataframe global unificat.  
4. **Diccionari de Segments:** Crear una correspondència (mapping) entre els IDs numèrics (1, 2, 3...).

## **3\. Local Segment CAD-RADS Scoring**

Ara que cada punt "sap" a quin segment pertany, hem de destil·lar la informació.

1. **Càlcul de Màxims**: Per a cada Segment\_ID únic, trobar el valor màxim de la columna pct\_AS.  
2. **Filtratge de Soroll**: Ignorar els segments amb Segment\_ID \= 0 (background).  
3. **Resum de l'Arbre**: Generar una taula resum on apareguin tots els segments presents en el pacient amb el seu percentatge d'estenosi més sever. Guardar aquesta informació com un dataframe i exportar-lo com a excel a la seva carpeta de resultats corresponent al bloc 3\. 

## **4\. Global Patient CAD-RADS Mapped Scoring**

#### **4.1. Determinació de l'Score Numèric Base (0-5)**

La classificació s'aplica a nivell de pacient basant-se en l'estenosi luminal més severa trobada en qualsevol segment de l'arbre coronari amb un diàmetre superior a 1,5 mm. S'assigna un valor numèric del 0 al 5 segons els següents llindars de reducció de l'àrea:

* **CAD-RADS 0:** Absència total de placa i estenosi (0%).  
* **CAD-RADS 1:** Estenosi mínima (1-24%) o placa sense estenosi.  
* **CAD-RADS 2:** Estenosi lleu (25-49%).  
* **CAD-RADS 3:** Estenosi moderada (50-69%).  
* **CAD-RADS 4:** Estenosi greu (70-99%).  
* **CAD-RADS 5:** Oclusió total d'almenys un vas (100%).

#### 

#### **4.2. Diferenciació Crítica: CAD-RADS 4A vs. 4B**

Per a pacients amb malaltia obstructiva, el sistema avalua l'extensió i la localització anatòmica per diferenciar entre lesions greus localitzades o malaltia d'alt risc:

* **CAD-RADS 4A:** Es designa quan existeix una estenosi greu (70-99%) en un o dos vasos principals.  
* **CAD-RADS 4B:** Aquesta categoria indica una situació de risc superior i s'assigna si es compleix alguna de les dues condicions següents:  
  * Presència d'una estenosi $\\ge 50\\%$ al **Tronc Comú (Segment 5 \- Left Main)**.  
  * Malaltia obstructiva de tres vasos, definida com estenosi $\\ge 70\\%$ en almenys un segment de cadascun dels tres territoris coronaris: RCA, LAD i LCX.

#### 

#### **4.3. Descriptor de Càrrega de Placa (P)**

Finalment, s'afegeix un modificador "P" per quantificar la quantitat total de placa ateroscleròtica a l'arbre coronari. S'utilitza el **Segment Involvement Score (SIS)**, calculat com el nombre total de segments (d'un màxim de 16\) que presenten qualsevol evidència de placa. L'score final es complementa amb el descriptor corresponent: **P1 (lleu, SIS ≤ 2\)**, **P2 (moderat, SIS 3-4)**, **P3 (greu, SIS 5-7)** o **P4 (extens, SIS ≥ 8\)**.

Aquest enfocament és robust perquè no només detecta la magnitud de l'estenosi, sinó que integra el risc clínic associat a la ubicació (com el Tronc Comú) i l'extensió global de la malaltia, proporcionant una eina de diagnòstic automatitzada i alineada amb els estàndards mèdics internacional.

## **5\. Generació d’Outputs**

El resultat final ha de ser útil per al metge.

1. **Informe de Pacient**: Generar un fitxer (PDF o JSON) que resumeixi:  
   * L'Score Global (p.e. **CAD-RADS 4B/P2**).  
   * La localització de la lesió més severa.  
   * El llistat de segments afectats.  
2. **Visualització Anatòmica**: Crear un gràfic 3D de l'arbre coronari on el color dels segments no sigui per %AS, sinó per Segment\_ID, per validar visualment que el mapeig és correcte.

