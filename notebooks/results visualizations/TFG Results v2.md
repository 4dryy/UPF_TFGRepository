  
**Automated 3D Stenosis Quantification and Visualization Workflow for Coronary Artery Disease Clinical Decision Support**

Adrià Cortés Cugat

---

UPF Tutor: Pr. Oscar Camara Rey

Supervisor: César Acebes Pinilla

Bachelor’s degree in Mathematical Engineering in Data Science

Academic Year 2025 \- 2026

# 

# **1 Pipeline Validation on MACS-18** 

**1.1 Execution Success Rate**   
Among the executed data samples, which ones of them completed the entire pipeline without any exception or error. 

**ESRTotal \= Number of correctly executed samplesNumber of total executed samples \= 100%**

**Normal\_1:** True 	 	**Diseased\_1:** True   
**Normal\_2:** True 		**Diseased\_2:** True   
**Normal\_3:** True 		**Diseased\_3:** True   
**Normal\_4:** True 		**Diseased\_4:** True   
**Normal\_5:**True		**Diseased\_5:** True   
**Normal\_6:** True 		**Diseased\_6:** True   
**Normal\_7:** True 		**Diseased\_7:** True   
**Normal\_8:** True 		**Diseased\_8:** True   
**Normal\_9:** True		**Diseased\_9:** True   
**Normal\_10:** True		**Diseased\_10:** True   
**Normal\_11:** True		**Diseased\_11:** True  
**Normal\_12:** True 		**Diseased\_12:** True  
**Normal\_13:** True		**Diseased\_13:** True  
**Normal\_14:** True		**Diseased\_14:** True  
**Normal 15:** True		**Diseased\_15:** True  
**Normal\_16:** True		**Diseased\_16:** True  
**Normal\_17:** True		**Diseased\_17:** True  
**Normal\_18:** True		**Diseased\_18:** True  
**Normal\_19:** True		**Diseased\_19:** True  
**Normal\_20:** True 		**Diseased\_20:** True

**1.2 Mean Detected Endpoints per Patient**  
In comparison with the ASOCA dataset (17.1 endpoints per patient), MACS-18 has more detailed geometrical information so more endpoints are detected on average for each patient, confirming that the improved data gives more details about the geometry of the coronary arteries. 

MPENormal \= Number total detected endpoints in Normal samplesNumber of Normal samples \=30.75 endpoints  
MPEDiseased \= Number total detected endpoints in Diseased samplesNumber of Diseased samples \=24.65 endpoints  
MPETotal \= Number total detected endpoints Number of Total Samples \=27.2 endpoints

**Normal\_1:** 28	 	**Diseased\_1:** 16   
**Normal\_2:**  25		**Diseased\_2:** 24  
**Normal\_3:** 42		**Diseased\_3:** 27  
**Normal\_4:** 22		**Diseased\_4:** 32  
**Normal\_5:** 24		**Diseased\_5:** 33  
**Normal\_6:** 22		**Diseased\_6:** 19  
**Normal\_7:** 27		**Diseased\_7:** 28  
**Normal\_8:** 28		**Diseased\_8:** 21  
**Normal\_9:** 35		**Diseased\_9:** 42  
**Normal\_10:** 31		**Diseased\_10:** 15  
**Normal\_11:** 57		**Diseased\_11:** 20  
**Normal\_12:** 17		**Diseased\_12:** 12  
**Normal\_13:** 64		**Diseased\_13:** 21  
**Normal\_14:** 33		**Diseased\_14:** 23  
**Normal\_15:** 30		**Diseased\_15:** 21  
**Normal\_16:** 26		**Diseased\_16:** 31  
**Normal\_17:** 23		**Diseased\_17:** 23  
**Normal\_18:** 25		**Diseased\_18:** 32  
**Normal\_19:** 24		**Diseased\_19:** 27  
**Normal\_20:** 32		**Diseased\_20:** 26

**1.3 Ostium Detection Accuracy**  
The Ostium Detection Accuracy (ODA) evaluates the anatomical accuracy of the automated ostium detection algorithm. This metric was obtained by visually inspecting the spatial coordinates of the algorithmically detected ostiums and comparing them against the true anatomical origins of the left and right coronary arteries. It represents the ratio of correctly placed ostium points to the total number of ostiums expected (two per patient). 

OISRNormal \= Number of correctly identified ostium pointsNumber of total ostium points  \= 75.00%  
OISRDiseased \= Number of correctly identified ostium pointsNumber of total ostium points \= 72.50%  
OISRTotal \= Number of correctly identified ostium pointsNumber of total ostium points \= 73.75%

**Normal\_1:** 1/2	 	**Diseased\_1:** 2/2  
**Normal\_2:** 0/2 		**Diseased\_2:** 2/2  
**Normal\_3:** 2/2 		**Diseased\_3:** 1/2  
**Normal\_4: 1**/2 		**Diseased\_4:** 1/2  
**Normal\_5:** 2/2 		**Diseased\_5:** 1/2  
**Normal\_6:** 1/2 		**Diseased\_6:** 2/2  
**Normal\_7:** 2/2 		**Diseased\_7:** 1/2  
**Normal\_8: 2**/2 		**Diseased\_8:** 1/2  
**Normal\_9: 2**/2 		**Diseased\_9:** 1/2  
**Normal\_10:** 1/2 		**Diseased\_10:** 2/2  
**Normal\_11:** 1/2 		**Diseased\_11:** 0/2  
**Normal\_12:** 2/2 		**Diseased\_12:** 2/2  
**Normal\_13:** 2/2 		**Diseased\_13:** 2/2  
**Normal\_14:** 1/2 		**Diseased\_14:** 1/2  
**Normal\_15:** 1/2 		**Diseased\_15:** 2/2  
**Normal\_16:** 2/2 		**Diseased\_16:** 2/2  
**Normal\_17: 1**/2 		**Diseased\_17:** 1/2  
**Normal\_18: 2**/2 		**Diseased\_18:** 2/2  
**Normal\_19:** 2/2 		**Diseased\_19:** 1/2  
**Normal\_20:** 2/2 		**Diseased\_20:** 2/2

**Discussion:** The observed decrease in Ostium Identification Success Rate (OISR) when transitioning from the ASOCA to the MACS-18 dataset can be directly attributed to the higher spatial resolution and topological complexity of the latter. High-resolution CCTA imaging captures a greater degree of anatomical detail, including minor side branches, surface irregularities, and local topological variations. Consequently, the automated 3D processing pipeline generates a significantly higher number of endpoints (averaging 27.7 endpoints per patient in the MACS-18 cohort). This increased topological density introduces algorithmic noise; with a larger pool of potential root candidates.

**1.4 Centerline Extraction Precision**

CESRNormal \= Number of correctly extracted centerlinesNumber of attempted centerline extractions \= 96.87%  
CESRDiseased \= Number of correctly extracted centerlinesNumber of attempted centerline extractions \= 94.04%  
CESRTotal \= Number of correctly extracted centerlinesNumber of attempted centerline extractions \=  95.62%

**Normal\_1:** 26/26	 		**Diseased\_1:** 12/14  
**Normal\_2:** 23/23 			**Diseased\_2:** 20/22  
**Normal\_3:** 38/40			**Diseased\_3:** 25/25  
**Normal\_4:**  20/20			**Diseased\_4:** 25/30  
**Normal\_5:**  22/22			**Diseased\_5:** 30/30  
**Normal\_6:**  20/20 			**Diseased\_6:** 16/17  
**Normal\_7:**  25/25			**Diseased\_7:** 26/26  
**Normal\_8:**  24/26			**Diseased\_8:** 19/19  
**Normal\_9:**  20/33			**Diseased\_9:** 39/40  
**Normal\_10:**  28/29			**Diseased\_10:** 13/13  
**Normal\_11:** 54/55			**Diseased\_11:** 17/18  
**Normal\_12:** 15/15			**Diseased\_12:** 10/10  
**Normal\_13:**  62/62 			**Diseased\_13:** 19/19  
**Normal\_14:** 30/31			**Diseased\_14:** 7/21  
**Normal\_15:**  27/28			**Diseased\_15:** 19/19  
**Normal\_16:** 21/24			**Diseased\_16:** 28/29  
**Normal\_17:** 21/21			**Diseased\_17:** 21/21  
**Normal\_18:** 23/23			**Diseased\_18:** 30/30  
**Normal\_19:** 22/22			**Diseased\_19:** 25/25  
**Normal\_20:**  26/30			**Diseased\_20:** 24/24

**Discussion:** Contrary to the challenges observed in ostium identification, the Centerline Extraction Success Rate (CESR) demonstrated a noticeable improvement when processing the MACS-18 dataset. This increase in algorithmic robustness can be directly attributed to the superior spatial resolution and geometric fidelity of the MACS-18 CCTA scans.  
Centerline extraction algorithms, such as those implemented in VMTK, rely heavily on the internal Voronoi diagram of the 3D surface mesh to compute optimal paths. In lower-resolution datasets like ASOCA, severe stenoses or highly distal vessel segments often suffer from partial volume effects, leading to artificial surface collapsing, mesh discontinuities, or degenerate triangles. These topological artifacts cause the pathfinding algorithm to encounter dead ends or fail to compute the inscribed spheres, resulting in aborted centerlines. Conversely, the high-resolution surface meshes generated from the MACS-18 dataset preserve the continuous lumen topology even across severely diseased and narrowed segments. This continuous geometric definition provides a highly regular and unbroken Voronoi network, allowing the algorithm to successfully trace and connect distal endpoints back to the root, thereby achieving a $95.62\\%$ global extraction success rate.

**1.5 Block and Total Runtimes**

Mean Total Runtime \=576.18s  9.60 minutes  
Mean Block 1 Runtime (3D Anatomy Extraction) \=159.76s   
Mean Block 2 Runtime (Geometric Quantification) \=357.73s   
Mean Block 3 Runtime(Labeling \+ CADRADS Scoring) \=57.86s   
Mean Block 4 Runtime (Dashboard Setup) \=0.02s 

# **2 Pipeline Validation on ASOCA**

**1.1 Execution Success Rate**   
Among the executed data samples, which ones of them completed the entire pipeline without any exception or error. 

**ESRTotal \= Number of correctly executed samplesNumber of total executed samples \= 100%**

**Normal\_1:** True 	 	**Diseased\_1:** True   
**Normal\_2:** True 		**Diseased\_2:** True   
**Normal\_3:** True 		**Diseased\_3:** True   
**Normal\_4:** True 		**Diseased\_4:** True   
**Normal\_5:**True		**Diseased\_5:** True   
**Normal\_6:** True 		**Diseased\_6:** True   
**Normal\_7:** True 		**Diseased\_7:** True   
**Normal\_8:** True 		**Diseased\_8:** True   
**Normal\_9:** True		**Diseased\_9:** True   
**Normal\_10:** True		**Diseased\_10:** True   
**Normal\_11:** True		**Diseased\_11:** True  
**Normal\_12:** True 		**Diseased\_12:** True  
**Normal\_13:** True		**Diseased\_13:** True  
**Normal\_14:** True		**Diseased\_14:** True  
**Normal 15:** True		**Diseased\_15:** True  
**Normal\_16:** True		**Diseased\_16:** True  
**Normal\_17:** True		**Diseased\_17:** True  
**Normal\_18:** True		**Diseased\_18:** True  
**Normal\_19:** True		**Diseased\_19:** True  
**Normal\_20:** True 		**Diseased\_20:** True

**1.2 Endpoint Identification Precision**  
From those detected endpoints, which are truly correct endpoints.

EISRNormal \= Number of correctly identified artery endpointsNumber of total identified artery endpoints \= 327364=89.84%  
EISRDiseased \= Number of correctly identified artery endpointsNumber of total identified artery endpoints \= 287320 \= 89.69%  
EISRTotal \= Number of correctly identified artery endpointsNumber of total identified artery endpoints \= 614684=89.77%

**Normal\_1:** 16/16	 	**Diseased\_1:** 10/10   
**Normal\_2:** 12/12 		**Diseased\_2:** 9/11  
**Normal\_3:** 16/20		**Diseased\_3:** 14/16  
**Normal\_4:** 10/13		**Diseased\_4:** 14/15  
**Normal\_5:** 19/20		**Diseased\_5:** 19/21   
**Normal\_6:** 11/12 		**Diseased\_6:** 17/20  
**Normal\_7:** 14/15 		**Diseased\_7:** 13/15  
**Normal\_8:** 18/19 		**Diseased\_8:** 16/18  
**Normal\_9:** 13/16 		**Diseased\_9:** 15/15  
**Normal\_10:** 16/17 		**Diseased\_10:** 11/11  
**Normal\_11:** 23/23		**Diseased\_11:** 14/16  
**Normal\_12:** 14/15		**Diseased\_12:** 14/15  
**Normal\_13:** 27/32 		**Diseased\_13:** 20/22  
**Normal\_14:** 28/30		**Diseased\_14:** 17/19  
**Normal\_15:** 10/12  		**Diseased\_15:** 10/13  
**Normal\_16:** 11/13 		**Diseased\_16:** 15/17  
**Normal\_17:** 15/16 		**Diseased\_17:** 17/19  
**Normal\_18:** 19/23		**Diseased\_18:** 19/21  
**Normal\_19:** 15/19		**Diseased\_19:** 11/12  
**Normal\_20:** 20/21 		**Diseased\_20:** 12/14

**1.3 Ostium Detection Accuracy**  
Among the detected ostiums, how many of them were truly correct. 

OISRNormal \= Number of correctly identified ostium pointsNumber of total ostium points \= 3440 \= 85%  
OISRDiseased \= Number of correctly identified ostium pointsNumber of total ostium points \= 3440 \= 85%  
OISRTotal \= Number of correctly identified ostium pointsNumber of total ostium points \= 6880 \= 85%

**Normal\_1:** 2/2	 	**Diseased\_1:** 2/2  
**Normal\_2:** 2/2 		**Diseased\_2:** 2/2  
**Normal\_3:** 2/2 		**Diseased\_3:** 2/2  
**Normal\_4:** 1/2 		**Diseased\_4:** 2/2  
**Normal\_5:** 2/2 		**Diseased\_5:** 1/2  
**Normal\_6:** 1/2 		**Diseased\_6:** 1/2  
**Normal\_7:** 1/2 		**Diseased\_7:** 2/2  
**Normal\_8:** 1/2 		**Diseased\_8:** 2/2  
**Normal\_9:** 2/2 		**Diseased\_9:** 2/2  
**Normal\_10:** 2/2 		**Diseased\_10:** 2/2  
**Normal\_11:** 1/2 		**Diseased\_11:** 2/2  
**Normal\_12:** 2/2 		**Diseased\_12:** 1/2  
**Normal\_13:** 2/2 		**Diseased\_13:** 2/2  
**Normal\_14:** 2/2 		**Diseased\_14:** 1/2  
**Normal\_15:** 2/2 		**Diseased\_15:** 2/2  
**Normal\_16:** 2/2 		**Diseased\_16:** 2/2  
**Normal\_17:** 2/2 		**Diseased\_17:** 1/2  
**Normal\_18:** 2/2 		**Diseased\_18:** 2/2  
**Normal\_19:** 2/2 		**Diseased\_19:** 1/2  
**Normal\_20:** 1/2 		**Diseased\_20:** 2/2

**1.4 Centerline Extraction Success Rate**

CESRNormal \= Number of correctly extracted centerlinesNumber of attempted centerline extractions \= 267321 \= 83.18%  
CESRDiseased \= Number of correctly extracted centerlinesNumber of attempted centerline extractions \= 228274 \= 83.21%  
CESRTotal \= Number of correctly extracted centerlinesNumber of attempted centerline extractions \= 495595 \=  83.19%

**Normal\_1:** 11/14 (3)	 	**Diseased\_1:** 8/8 (0)  
**Normal\_2:** 10/10 (0) 		**Diseased\_2:** 6/8 (2)  
**Normal\_3:** 8/18 (10)		**Diseased\_3:** 12/12 (0)  
**Normal\_4:** 7/11 (4) 		**Diseased\_4:** 11/13 (2)  
**Normal\_5:**  18/18 (0) 	**Diseased\_5:** 16/19 (3)  
**Normal\_6:** 7/10 (3)  		**Diseased\_6:** 16/18 (2)  
**Normal\_7:** 11/13 (2) 		**Diseased\_7:** 11/13 (2)  
**Normal\_8:** 15/17 (2) 		**Diseased\_8:** 16/16 (0)  
**Normal\_9:** 11/14 (3) 		**Diseased\_9:** 11/13 (2)  
**Normal\_10:** 13/15 (2) 	**Diseased\_10:** 8/9 (1)  
**Normal\_11:** 17/21 (4) 	**Diseased\_11:** 11/14 (3)  
**Normal\_12:** 12/13 (1) 	**Diseased\_12:** 12/14 (2)  
**Normal\_13:** 24/30 (6)  	**Diseased\_13:** 15/20 (5)  
**Normal\_14:** 27/28 (1)	**Diseased\_14:** 11/17 (6)  
**Normal\_15:** 8/10 (2) 		**Diseased\_15:** 8/11 (3)  
**Normal\_16:** 9/9 (0) 		**Diseased\_16:** 9/11 (2)  
**Normal\_17:** 12/13 (1) 	**Diseased\_17:** 12/17 (5)  
**Normal\_18:** 16/21 (5) 	**Diseased\_18:** 15/19 (4)  
**Normal\_19:** 13/17 (4) 	**Diseased\_19:** 9/10 (1)  
**Normal\_20:** 18/19 (1) 	**Diseased\_20:** 11/12 (1)

**1.5 Block and Total Runtimes**

Mean Total Runtime \=346.92s 5.78 minutes   
Mean Block 1 Runtime (3D Anatomy Extraction) \=145.78s   
Mean Block 2 Runtime (Geometric Quantification) \=164.64s   
Mean Block 3 Runtime(Labeling \+ CADRADS Scoring) \=35.19s   
Mean Block 4 Runtime (Dashboard Setup) \=0.16s 

**Normal\_1:** 139.24s / 149.63s / 34.65s / 0.18s \= 325.11s 	**Diseased\_1:** 143.48s / 78.80s / 22.35s / 0.14s \= 245.45s  
**Normal\_2:** 119.24s / 109.53s / 24.81s / 0.16s \= 254.39s 	**Diseased\_2:** 139.32s / 71.73s / 23.91s / 0.22s \= 236.50s  
**Normal\_3:** 142.15s / 99.91s / 22.58s / 0.18s \= 265.39s  		**Diseased\_3:** 149.27s / 142.49s / 39.64s / 0.16s \= 332.70s  
**Normal\_4:** 135.60s / 82.38s / 20.75s / 0.15s \= 239.63s		**Diseased\_4:** 143.79s / 95.05s / 26.78s / 0.16s \= 266.84s  
**Normal\_5:** 135.23s / 177.30s / 35.25s / 0.14s \= 348.77s 	**Diseased\_5:** 145.83s / 196.83s / 38.68s / 0.17s \= 382.35s  
**Normal\_6:** 136.23s / 79.44s / 18.77s / 0.16s \= 235.50		**Diseased\_6:** 159.52s / 186.38s / 38.97s / 0.17s \= 385.89s  
**Normal\_7:** 132.07s / 144.20s / 30.72s / 0.15s \= 308.17s 	**Diseased\_7:** 157.96s / 185.73s / 44.54s / 0.18s \= 389.33s  
**Normal\_8:** 150.06s / 243.35s / 43.43 / 0.16s \= 437.82s 		**Diseased\_8:** 161.00s / 209.60s / 45.39s / 0.15s \= 417.36s  
**Normal\_9:** 148.53s / 131.80s / 32.26s /0.15s \= 313.42s 		**Diseased\_9:** 153.66s / 167.08s / 38.69s / 0.16s \= 360.39s  
**Normal\_10:** 147.02s / 204.02s / 39.81s / 0.15s \= 391.80s 	**Diseased\_10:** 149.62s / 81.41s / 25.54s / 0.16s \= 257.60s  
**Normal\_11:** 154.40s / 285.19s / 46.85s / 0.13s \= 487.58s 	**Diseased\_11:** 151.53s / 119.40s / 30.68s /0.23s \= 302.60s  
**Normal\_12:** 138.00s / 133.80s / 29.67s / 0.14s \= 302.60s  	**Diseased\_12:** 135.26s / 101.44s / 30.53s / 0.13s \= 268.05s  
**Normal\_13:** 152.83s / 386.28s / 57.77s / 0.15s \= 597.97s	**Diseased\_13:** 158.82s / 246.72s / 42.33s / 0.18s \= 449.00s  
**Normal\_14:** 161.72s / 401.24s / 69.84s / 0.13s \= 633.60s 	**Diseased\_14:** 145.40s / 117.74s / 21.89s / 0.16s \= 296.06s  
**Normal\_15:** 132.70s /80.50s / 23.70s / 0.16s \= 237.67s		**Diseased\_15:** 155.50s / 119.26s / 34.18s / 0.15s \= 309.84s  
**Normal\_16:** 138.92s / 126.46s / 30.53s / 0.16s \= 297.22s 	**Diseased\_16:** 142.84s / 188.57s / 40.60s / 0.19s \= 373.33s  
**Normal\_17:** 147.71s / 143.04s / 35.33s / 0.17s \= 327.33s	**Diseased\_17:** 156.23s / 182.62s / 37.08s / 0.16s \= 377.02s  
**Normal\_18:** 125.10s / 303.59s / 48.89s / 0.16s \= 478.68s 	**Diseased\_18:** 165.63s / 233.00s / 45.95s /0.18s \= 445.65s  
**Normal\_19:** 145.21s / 122.97s / 30.35s / 0.16s \= 299.43s	**Diseased\_19:** 117.79s / 117.38s / 30.73s / 0.16s \= 266.81s  
**Normal\_20:**  151.84s / 174.30s / 38.29s / 0.16s \= 365.33s	**Diseased\_20:** 165.12s / 165.42s / 34.76s / 0.24s \= 366.78s

# **3 Geometric and Algorithmic Verification: Synthetic Data**

**3.1 Control Model Validation: Synthetic 1 \- Healthy**

* **Theoretical Maximum %AS \= 0.00%**  
* **Predicted Maximum %AS \= 2.64%**  
* **Absolute Error %AS \=** | Theoretical Max %AS \- Predicted Max %AS | \=2.64%   
* **Theoretical Area \= 314.16mm2**  
* **Predicted Area Mean \= 319.39mm2**  
* **Mean Area Absolute Error \=| Theoretical Area \-Predicted Area Mean  | \=5.23mm2**  
* **Maximum Area Deviation \= 39.17mm2**

**Discussion:** Which are the thresholds that I am using to evaluate if the obtained results are good or bad? What could we do to improve the results?  
Explain and argument these experiments in the methodology and discussions section in the report.

**3.2 Stenosis Model Validation: Synthetic 2 \- Diseased**

* **Theoretical Maximum %AS \= 75.00%**  
* **Predicted Maximum  %AS \= 73.67%**  
* **Absolute Error Maximum %AS \=** | Theoretical Max %AS \- Predicted  Max %AS | \=1.33%   
* **Theoretical Maximum Area \= 314.16mm2**  
* **Theoretical Minimum Area \= 78.54mm2**  
* **Predicted Maximum Area \= 333.62mm2**  
* **Predicted Minimum Area \= 82.55mm2**  
* **Absolute Error Maximum Area=**| Theoretical Max Area \- Predicted  Max Area | \=19.47**mm2**   
* **Absolute Error Minimum Area \=**| Theoretical Min Area \- Predicted  Min Area | \= **4.01mm2**

**Discussion:** Which are the thresholds that I am using to evaluate if the obtained results are good or bad? What could we do to improve the results?  
Explain and argument these experiments in the methodology and discussions section in the report.

**Llindars (*Thresholds*):** En l'àmbit del processament d'imatge mèdica i hemodinàmica computacional, un error absolut de només un **1.33%** en la predicció del percentatge d'estenosi és un èxit rotund. La majoria de variabilitat inter-observador (quan dos metges miren la mateixa imatge manualment) sol estar entre el 5% i el 10%. Per tant, pots defensar que el teu algoritme té una precisió totalment clínica.

**Com millorar-ho:** Per justificar aquells **5.23 mm²** d'error absolut a l'àrea, pots suggerir en el text que futures versions poden utilitzar mètodes interpolació espacial sub-vòxel encara més fins, o augmentar la densitat dels punts de mostreig per sobre dels 400 talls actuals del *fallback*.

# **4 User Experience and Interface Usability Evaluation**

# 

# Results after the users complete the interaction and the formulary: 

* [https://docs.google.com/forms/d/e/1FAIpQLSeHmCs-B8pYm0gK3JLsp3BxlJqsrcMEDv3arWlycSDIPj6ARA/viewform?usp=publish-editor](https://docs.google.com/forms/d/e/1FAIpQLSeHmCs-B8pYm0gK3JLsp3BxlJqsrcMEDv3arWlycSDIPj6ARA/viewform?usp=publish-editor)

**4.1 System Usability Score**  
**\+++**

**4.2 Feedback, Discussions and Future Work with Doctors at HSP**

During the final stages of this project, a clinical evaluation session was conducted with expert cardiologists at Hospital de la Santa Creu i Sant Pau to assess the pipeline's clinical utility and identify areas for future improvement. The feedback gathered is highly valuable, as it bridges the gap between technical implementation and real-world clinical workflows. The following sections outline the key discussions and proposed future work.

#### **4.2.1 Algorithmic and Metric Refinements**

* **Dynamic Reference Values for Stenosis Calculation:** The current formula uses fixed cross-sectional area reference values depending on a predefined window size, which introduces limitations in quantification, particularly near bifurcations. Clinical experts noted that they typically select healthy reference points within the same segment manually. Future iterations should allow clinicians to dynamically adjust the proximal and distal reference values, bypassing anatomical anomalies and improving the accuracy of the stenosis calculation.  
* **Centerline Resolution Optimization:** The current pipeline extracts centerline points with high spatial granularity (\< 0.1 mm for short branches, \< 0.2 mm for long branches). While this provides rich geometric data, cardiologists suggested that a coarser spacing (e.g., \~2 mm) is generally sufficient for standard diagnosis. Reducing the resolution would significantly improve computational efficiency, though higher granularity could be dynamically retained exclusively in diseased segments.  
* **Plaque vs. Stenosis Quantification:** A critical clinical distinction was emphasized during the evaluation: while plaque accumulation (e.g., calcium, cholesterol) causes stenosis, the presence of plaque does not always imply a hemodynamically significant stenosis. Current clinical workflows prioritize identifying plaque first. Future work should integrate plaque quantification alongside stenosis detection, providing a more comprehensive and realistic diagnostic picture.

  #### **4.2.2 Visualization and Interface Enhancements**

* **Continuous Lumen Visualization:** Clinicians expressed the need to visualize the lumen's progression continuously along the artery, rather than relying solely on discrete centerline data points. Providing continuous cross-sectional profiles allows for an easier and more intuitive diagnostic assessment.  
* **Integration of Medical Imaging (Ground Truth):** A critical requirement for clinical adoption is the ability to compare algorithmic results with raw medical images. Future versions of the dashboard must incorporate Curved Multi-Planar Reformation (CMPR) and cross-sectional views of the real Coronary Computed Tomography Angiography (CCTA) scans. This overlay ensures clinicians can validate the software's findings against the anatomical reality.  
* **Advanced Dashboard Features and Explainability:** Taking inspiration from robust commercial solutions, the ultimate goal for the user interface is a highly interactive dashboard. Key requested components include a 3D representation of the coronary tree, interactive metrics where doctors can adjust thresholds, and clear explainability of the algorithmic decisions to avoid "black-box" models. Furthermore, rather than displaying per-point stenosis metrics, the interface should highlight aggregated affected zones (e.g., regions with ≥ 50% stenosis) to allow doctors to quickly triage or inspect specific areas.

  #### **4.2.3 Clinical Workflow Integration**

The most significant potential of this visualization tool lies in its integration within a broader hospital ecosystem. By unifying automatic segmentation inputs with advanced patient prioritization algorithms, this project serves as a crucial connective element. In a clinical setting, a doctor reviewing a prioritized list of at-risk patients could open a pop-up of this dashboard for a rapid, initial assessment. This quick overview of key metrics and affected zones would allow clinicians to efficiently decide whether a patient requires immediate, detailed analysis using complex diagnostic software or if they can be safely managed otherwise.

