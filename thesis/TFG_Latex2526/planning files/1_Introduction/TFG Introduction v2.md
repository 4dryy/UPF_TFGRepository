  
**Automated Geometric Stenosis Quantification and CAD-RADS Support for Coronary Artery Disease Assessment and Patient Prioritization**

Adrià Cortés Cugat

---

UPF Tutor: Pr. Oscar Camara Rey

Supervisor: César Acebes Pinilla

Bachelor’s degree in Mathematical Engineering in Data Science

Academic Year 2025 \- 2026

# 

# **1 Introduction**

## **1.1 Clinical Context and Motivation**

## **1.1.1 Anatomy of Coronary Arteries**

The human heart is the central organ of the cardiovascular system and requires a continuous supply of oxygen and nutrients to function properly. This supply is provided by the coronary artery tree, a specialized vascular network that delivers blood directly to the heart muscle, known as the myocardium. The coronary arteries originate from the root of the aorta and surround the surface of the heart in a crown-like arrangement, from which the term coronary artery is derived \[1\]. As illustrated in Figure 1, the coronary arterial system is mainly composed of two vessels: the right coronary artery (RCA) and the left coronary artery (LCA). 

## 

**Figure 1\.** Anterior view of the human coronary tree. Coronary arteries are highlighted in red, and other cardiac structures in blue. Adapted from P. J. Lynch et al. \[1\].

The RCA primarily supplies blood to the right atrium and right ventricle. In contrast, the LCA quickly divides into two major branches: the left anterior descending (LAD) artery and the circumflex (LCx), which together supply the majority of the left ventricle and the interventricular septum \[1\]. From these primary vessels, a network of smaller branches extends deep into the myocardium to ensure regional blood delivery across the entire heart. 

A critical characteristic of the coronary circulation is its limited collateral connectivity. Unlike other vascular systems in the human body, coronary arteries generally lack sufficient alternative pathways to redirect blood flow when an obstruction occurs. Consequently, any narrowing or blockage in a proximal arterial segment directly compromises blood flow to all downstream regions supplied by that vessel \[2\].

Additionally, coronary anatomy presents significant inter-patient variability in terms of vessel size, branching structure, and coronary dominance. Dominance is defined by which artery gives rise to the posterior descending artery (PDA) and can be classified as right-dominant, left-dominant, or codominant. Right-dominant circulation, in which the PDA originates from the RCA, is the most common configuration, followed by left dominance and codominance \[3\]. Understanding this complex anatomical layout is fundamental, as it provides the basis for locating lesions, quantifying stenosis severity, and stratifying risk in coronary artery disease (CAD) diagnosis.

**1.1.2 Coronary Artery Disease**

Coronary artery disease (CAD) remains one of the leading causes of morbidity and mortality worldwide \[6\]. It is characterized by the progressive accumulation of atherosclerotic plaque within the walls of the coronary arteries, leading to a narrowing of the vessel lumen known as stenosis. This narrowing restricts blood flow to the myocardium and, if left untreated, can result in a myocardial ischemia or infarction \[7, 8\]. Figure 2 illustrates this pathological mechanism, contrasting a normal artery with one obstructed by plaque buildup. 

**Figure 2**. Coronary arteries narrowed by atherosclerotic plaque. Adapted from Kaiser Permanente \[5\]. 

Early and accurate diagnosis is essential for effective risk stratification and patient management. In current clinical practice, coronary computed tomography angiography (CCTA) is the standard non-invasive imaging technique for CAD evaluation \[7\]. CCTA provides detailed 3D reconstructions of the coronary tree, allowing clinicians to detect plaques, analyze their spatial location, and estimate the degree of luminal narrowing. 

However, despite the high resolution of CCTA, the diagnostic workflow remains highly time-consuming and heavily dependent on manual and visual assessment. For instance, at Hospital de la Santa Creu i Sant Pau, reporting non-pathological or low-complexity cases requires approximately 30 minutes, while complex evaluations can take up to 2 hours \[9\]. This significant clinical burden drives the need for automated, data-driven tools capable of quantifying stenosis efficiently and supporting clinical decision-making, while fully preserving expert interpretability and clinical control.

**1.1.3 Stenosis Quantification: A Key Indicator of CAD Severity**

Among the various indicators used to assess coronary artery disease, stenosis severity plays a central role in clinical diagnosis and risk stratification. Stenosis represents the reduction of the vessel lumen caused by atherosclerotic plaque accumulation, a condition directly associated with an increased risk of myocardial ischemia and adverse cardiac events \[7, 10\]. In clinical practice, this severity is quantified using geometric measurements such as the minimal lumen area (MLA) or percentage diameter stenosis (%DS). These metrics evaluate the degree of narrowing by comparing the most constricted point of a lesion with a reference baseline, which is typically estimated from adjacent, relatively healthy vessel segments \[10, 11\]. 

Although these definitions are conceptually simple, accurate stenosis quantification presents significant clinical challenges. Coronary arteries exhibit complex, tortuous geometries, and diffuse atherosclerosis often makes it difficult to identify truly healthy reference regions. In addition, limitations in image resolution, segmentation errors, and noise in CCTA-derived data can highly influence measurements, leading to variability in stenosis estimates \[12, 11\].  
In routine clinical practice, stenosis assessment is often performed visually or using semi-automatic tools provided by proprietary software \[9, 13\]. Although these methods are widely used, they depend heavily on the clinician’s interpretation and can vary between observers, which reduces consistency and reproducibility \[11\].  

Consequently, there is a strong clinical need to develop robust, transparent, and reproducible quantification methods. Automating these geometric measurements has the potential to standardize stenosis evaluation, reduce reporting time, and provide reliable quantitative data essential for downstream clinical tasks, such as CAD-RADS 2.0 assignment and patient prioritization.

**1.1.4 CAD RADS 2.0 and the Need for Decision Support** 

To standardize the reporting of coronary disease and facilitate clinical communication, the Coronary Artery Disease-Reporting and Data System (CAD-RADS 2.0) was established \[13\]. This structured framework categorizes patients into distinct risk scores ranging from 0 to 5, primarily based on the most severe stenosis measured via CCTA. Each categorical score reflects the overall disease burden and provides specific clinical recommendations, offering a standardized pathway for subsequent patient management \[13\].

While CAD-RADS 2.0 significantly improves reporting consistency across institutions, its assignment still relies heavily on the manual interpretation of stenosis severity across multiple vessels and segments. This process requires clinicians to continuously synthesize quantitative geometric measurements with complex anatomical context. Consequently, evaluating these scans becomes highly cognitively demanding, particularly in time-constrained clinical environments \[9\]. In practice, manual scoring remains susceptible to inter-observer variability, especially in borderline cases or in patients presenting with multiple moderate lesions. Such discrepancies can lead to inconsistent diagnostic classifications, ultimately impacting downstream clinical decisions, further testing, and patient prioritization \[9, 11\].

To address these limitations, there is a growing clinical imperative to develop automated decision support tools. These solutions can span from rule-based algorithms mapping quantitative stenosis measurements to machine learning approaches that leverage structured imaging features. Crucially, these computational tools aim to provide objective, reproducible, and transparent suggestions to assist radiologists and cardiologists. By streamlining the CAD-RADS assignment process, these systems reduce reporting times and variability while strictly preserving expert clinical judgment and final decision authority. 

## 

## 

## **1.2 Clinical Automation Challenges at Hospital de la Santa Creu i Sant Pau**

**1.2.1 Current CAD Diagnostic Workflow and Associated Limitations** 

The current diagnostic workflow for Coronary Artery Disease (CAD) at Hospital de la Santa Creu i Sant Pau involves a complex and coordinated series of steps, managed by primarily the specialized cardiac imaging unit (Unitat d’Imatge i Funció Cardíaca, UIFC). As illustrated in Figure 3, the clinical pathway begins when a patient presenting with symptoms such as chest pain is scheduled for a Coronary Computed Tomography Angiography (CCTA). Once the scan is acquired, the images are stored in the hospital’s *Picture Archiving and Communication System (PACS)* for further evaluation. 

**Figure 3\.** Current CAD diagnostic workflow at Hospital de Sant Pau. The primary operational bottleneck (image assessment and reporting) is highlighted in red. Adapted from Ferrer Beltran \[14\]

The core of this diagnostic pipeline relies heavily on the visual and manual analysis of these scans by expert cardiologists and radiologists to extract clinical metrics. These findings are then compiled into a clinical report, which the referring clinician evaluates to determine the appropriate subsequent medical actions, ranging from discharging a healthy patient to programming further invasive tests.   
While the overall infrastructure is well-established, the central phase of image analysis and reporting (highlighted in red in Figure 3\) represents a critical operational bottleneck. 

**1.2.2 The Bottleneck: Manual Image Analysis and Reporting**  
   
Zooming into the specific image analysis and reporting phase (Figure 3), the limitations of the current clinical pathway become evident. Currently, clinicians rely on commercial software solutions, such as *syngo.via*, to manually inspect the coronary arteries, differentiate segments, and calculate stenosis severity. Although these platforms offer semi-automated tools, the process remains highly dependent on the clinician’s expertise to visually verify the vessels, identify bifurcations, and assess the plaque burden. Depending on the anatomical complexity and image quality, analyzing a single patient can consume around 30 minutes for healthy cases and 90 minutes for complex cases \[9\].

Once the visual assessment is complete, the extracted metrics are manually entered into an internal custom-built platform called *Filemaker,* which generates a template-based preliminary report. The specialist must then review, correct, and finalize this text before it is integrated into the *Radiology Information System (RIS)*. 

**Figure 4\.** Detailed representation of the image analysis and reporting workflow at Hospital de Sant Pau. Adapted from Acebes Pinilla \[9\]. 

This heavy reliance on manual quantification and data entry presents significant operational challenges. Consequently, highly specialized experts spend considerable time performing repetitive, manual tasks on low-risk patients, rather than focusing their expertise on critical cases. This lack of an automated, prioritized workflow delays the diagnosis of severe cases and highlights a clear necessity for robust and automated solutions. 

## **1.3  State of The Art: Automation of CAD Diagnosis and Visualization**

The integration of Artificial Intelligence (AI) and advanced computer vision in cardiac imaging has seen exponential growth over the past decade, driven by the need to optimize clinical workflows \[15\]. Deep learning algorithms, particularly Convolutional Neural Networks (CNNs), have demonstrated remarkable success in medical image analysis, encouraging a move from manual CCTA assessment to automated systems \[16\]. However, significant limitations remain regarding their practical implementation. For these new techniques to succeed, they must be practical for hospitals, integrate smoothly into current systems, and be easily adopted by the clinical staff \[23\]. 

The prerequisite first step in any automated CAD assessment pipeline is the accurate segmentation and anatomical labeling of the coronary artery tree; before any downstream diagnostic metric can be calculated, the vessels must be correctly isolated and identified. Recent advancements have leveraged deep learning architectures, such as 3D U-Nets, to extract the vessel lumen from CCTA images \[18, 26\], while graph-based models like Graph Convolutional Networks (GCNs) are increasingly used to ensure topological consistency when labeling segments according to standard clinical guidelines \[27\]. Within Hospital de la Santa Creu i Sant Pau, preliminary research has explored these initial segmentation and labeling tasks using transformer-based models and the nn-UNet framework \[21, 28\].

Following successful segmentation, extracting the precise geometric properties of the vessels is essential. The Vascular Modeling Toolkit (VMTK) stands out as one of the most prominent open-source libraries for medical geometry data extraction \[17\]. Specifically, algorithms implemented within VMTK are widely utilized to extract accurate vascular centerlines and compute cross-sectional areas. These metrics provide the essential topological framework required to perform continuous Multi-Planar Reformations and subsequently evaluate vessel narrowing.

Once the 3D geometry of the coronary tree is established, the focus shifts to quantifying the disease burden. Current stenosis quantification techniques range from traditional intensity-based thresholding (which often struggles with severe calcifications) to modern machine learning models that predict stenosis severity directly from image features \[18, 19\]. Alternatively, geometric, non-ML approaches offer highly interpretable and robust methods by calculating the percentage of diameter or area stenosis based purely on the physical vessel profile, comparing the minimal lumen area against an interpolated healthy reference \[11\]. Recognizing the clinical value of algorithmic transparency, ongoing research at Hospital de la Santa Creu i Sant Pau has actively explored these purely geometric techniques to quantify stenosis, establishing a reliable, explainable foundation for disease assessment \[22\]. 

Beyond quantification, the effective visualization of these complex 3D metrics remains a critical challenge in the state of the art \[20\]. In the current clinical routine at Hospital de Sant Pau, specialists must manually navigate through cross-sectional slices and use standard viewing software to visually synthesize the data, assess the lesions, and manually fill out structured reports \[9\]. This cognitive load highlights a significant gap: the lack of dedicated, interactive visualization tools that bridge the gap between automated metrics and clinical reality. Modern research and clinical consensus emphasize that integrating 3D anatomical models alongside continuous luminal profiles and real medical images (such as Curved Multi-Planar Reformations) into a unified graphical interface is essential. Such integration allows clinicians to continuously validate automated findings against the ground-truth CCTA, drastically reducing the time and effort required to verify stenosis locations and seamlessly generate diagnostic reports \[20\].

Several commercial software solutions have emerged to address these overarching needs, including platforms like *Cleerly* \[25\] and *Artrya Salix* \[29\], which use AI to analyze arterial plaque and assess ischemia risk from CCTA images. While these robust dashboards offer highly desirable visualization components, they often function as proprietary “black boxes”. This lack of algorithmic transparency significantly hinders explainability, a feature strongly demanded by medical experts to verify how a specific CAD-RADS score, plaque distribution, or stenosis percentage was computed. Finally, these standalone commercial platforms frequently struggle to integrate well into the highly specific IT infrastructures and patient prioritization workflows of public hospitals \[23\].

## **1.4 Project Scope and Contributions**

To address the clinical challenges outlined in Section 1.2, and to overcome the limitations of commercial tools discussed in Section 1.3, this project contributes directly to the comprehensive, transparent, and in-house AI-enabled diagnostic framework developed by the Dimension Lab at Hospital de la Santa Creu i Sant Pau \[9\]. While previous academic efforts have tackled earlier stages of this pipeline, such as patient prioritization \[14\] and coronary artery segmentation and labeling \[21\], a critical gap remains in translating raw segmented geometries into actionable clinical insights.

Therefore, the scope of this bachelor's thesis focuses on automating the geometric quantification of coronary stenosis, predicting the associated CAD-RADS score, and integrating these findings into an interactive clinical dashboard.

Figure 5 provides a high-level overview of where this project sits within the pipeline, while the detailed technical workflow is reserved for the Methods chapter. 

**Figure 5\.** Contextual overview of the proposed automated diagnostic framework at Hospital de la Santa Creu i Sant Pau. The contributions of this thesis (green dashed box) bridge the gap between existing hospital data systems (blue) and the final clinical report. Adapted from Acebes Pinilla \[9\]. 

By seamlessly connecting raw image analysis with the hospital's reporting systems, this project aims to mitigate operational bottlenecks and reduce overall diagnostic times. 

However, it is crucial to emphasize that the solution developed in this project is intended solely as a clinical decision-support tool, not as a replacement for medical expertise. In the highly sensitive healthcare sector, human oversight is crucial. Rather than replacing detailed diagnostic software, this visualization tool is designed to act as a rapid initial assessment interface. By presenting an immediate, high-level overview of the patient's critical metrics, it assists specialists in quickly evaluating prioritized patient lists, helping them decide which cases require immediate, in-depth analysis. Thus, the automated findings are designed to streamline the workflow, ensuring that the final diagnostic decisions and clinical validations always remain firmly in the hands of the medical professionals.  
 

## **1.5 Objectives**

The primary objective of this thesis is to design and develop an automated, end-to-end pipeline that successfully bridges the current gap in the CAD diagnostic workflow. Importantly, this project does not seek to maximize the precision of individual algorithmic components; rather, the proposed functional workflow is, in itself, the core product of this work.

To achieve this overarching goal, the project addresses a sequence of intermediate objectives. First, it requires deep contextualization within the complex clinical environment to evaluate prior research conducted at the hospital and design a unified, clinically applicable framework. Building upon this foundation, the project aims to implement computational geometry algorithms to accurately extract cross-sectional areas and calculate the percentage of area stenosis from 3D models. Subsequently, a standardized logic is developed to translate these geometric metrics into a reliable CAD-RADS score prediction. 

To aggregate these findings and provide cardiologists with interpretable metrics, an interactive clinical dashboard is built. This Support Visualization Tool is designed to strike a balance between the hospital's specific reporting requirements and the technical focus of this project, ultimately aiming to reduce medical workload and assessment time. Finally, a technical validation is conducted to verify the reliability of the extracted metrics and ensure the overall stability of the complete framework.

To aggregate these findings and provide cardiologists with interpretable metrics, an interactive clinical dashboard is built. Functioning as a rapid-access pop-up interface, this Support Visualization Tool gives clinicians an immediate, visual summary of the patient's coronary status, ultimately reducing medical workload, optimizing case triaging, and significantly decreasing overall assessment time. 

**References**

**\[1\]**  Coronary Arteries: Anatomy and Function. URL: [https://my.clevelandclinic.org/health/body/22973-coronary-arteries](https://my.clevelandclinic.org/health/body/22973-coronary-arteries)

**\[2\]** Seiler, C. (2010). The human coronary collateral circulation. *European journal of clinical investigation*, *40*(5), 465-476. [https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1365-2362.2010.02282.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1365-2362.2010.02282.x)

**\[3\]** Wu, B., Kheiwa, A., Swamy, P., Mamas, M. A., Tedford, R. J., Alasnag, M., ... & Abramov, D. (2024). Clinical significance of coronary arterial dominance: a review of the literature. *Journal of the American Heart Association*, *13*(9), e032851. [https://www.ahajournals.org/doi/full/10.1161/JAHA.123.032851](https://www.ahajournals.org/doi/full/10.1161/JAHA.123.032851)

**\[4\]** Lynch, P. J., Fred the Oyster, & Häggström, M. (2010). Coronary circulation in anterior view \[Medical illustration\]. Wikimedia Commons. [https://commons.wikimedia.org/wiki/File:Coronary\_arteries.png](https://commons.wikimedia.org/wiki/File:Coronary_arteries.png) 

**\[5\]** Kaiser Permanente. (n.d.). *Cardiology \- Artery with Atherosclerosis \- TPMG* \[Medical illustration\]. Coronary Artery Bypass Graft Surgery \- CV Surgery.  
[https://mydoctor.kaiserpermanente.org/mas/structured-content/Procedure\_Coronary\_Artery\_Bypass\_Graft\_Surgery\_-\_CV\_Surgery.xml?co=%2Fregions%2Fmas](https://mydoctor.kaiserpermanente.org/mas/structured-content/Procedure_Coronary_Artery_Bypass_Graft_Surgery_-_CV_Surgery.xml?co=%2Fregions%2Fmas)

**\[6\]** World Health Organization. (2023). Cardiovascular diseases (CVDs). [https://www.who.int/health-topics/cardiovascular-diseases\#tab=tab\_1](https://www.who.int/health-topics/cardiovascular-diseases#tab=tab_1)

**\[7\]** Knuuti, J., Wijns, W., Saraste, A., Capodanno, D., Barbato, E., Funck-Brentano, C., ... & ESC Scientific Document Group. (2020). 2019 ESC Guidelines for the diagnosis and management of chronic coronary syndromes. *European Heart Journal*, 41(3), 407-477. [https://doi.org/10.1093/eurheartj/ehz425](https://doi.org/10.1093/eurheartj/ehz425) 

**\[8\]** McCullough, P. A. (2007). Coronary artery disease. *Clinical Journal of the American Society of Nephrology*, *2*(3), 611-616.  [https://journals.lww.com/cjasn/abstract/2007/05000/coronary\_artery\_disease.30.aspx](https://journals.lww.com/cjasn/abstract/2007/05000/coronary_artery_disease.30.aspx)

**\[9\]** Acebes Pinilla, C. (2024). *An artificial intelligence framework for the prioritization and reporting of coronary artery disease patients in a cardiac imaging unit* \[Presentation\]. Hospital de la Santa Creu i Sant Pau, Dimension Lab. 

**\[10\]** Garcia-Garcia, H. M., Costa, M. A., & Serruys, P. W. (2014). Assessment of coronary artery disease by intravascular imaging. *European Heart Journal*, 35(35), 2321-2330. [https://doi.org/10.1093/eurheartj/ehu081](https://doi.org/10.1093/eurheartj/ehu081) 

**\[11\]** Hideo-Kajita, A., Wopperer, S., Beyene, S. S., Meirovich, Y. F., Melaku, G. D., Kuku, K. O., ... & Garcia-Garcia, H. M. (2019). Impact of two formulas to calculate percentage diameter stenosis of coronary lesions: from stenosis models (phantom lesion model) to actual clinical lesions. *The International Journal of Cardiovascular Imaging*, 35(12), 2139–2146. [https://doi.org/10.1007/s10554-019-01672-z](https://doi.org/10.1007/s10554-019-01672-z) 

**\[12\]** Kalisz, K., Buethe, J., Saboo, S. S., Abbara, S., Halliburton, S., & Rajiah, P. (2016). Artifacts at Cardiac CT: Physics and Solutions. *RadioGraphics*, 36(7), 2064-2083. [https://doi.org/10.1148/rg.2016160079](https://doi.org/10.1148/rg.2016160079) 

**\[13\]** Cury, R. C., Abbara, S., Achenbach, S., Agatston, A., Berman, D. S., Budoff, M. J., ... & Blankstein, R. (2022). CAD-RADS™ 2.0–2022 Coronary Artery Disease-Reporting and Data System. *Journal of Cardiovascular Computed Tomography*, 16(6), 536-557. [https://doi.org/10.1016/j.jcct.2022.07.002](https://www.google.com/search?q=https://doi.org/10.1016/j.jcct.2022.07.002) 

**\[14\]** Ferrer Beltran, E. (2024). *Enhanced Prioritization and Reporting for Coronary Artery Disease Diagnosis* \[Bachelor's thesis, Universitat Pompeu Fabra\]. 

**\[15\]** Litjens, G., Kooi, T., Bejnordi, B. E., Setio, A. A. A., Ciompi, F., Ghafoorian, M., ... & Sánchez, C. I. (2017). A survey on deep learning in medical image analysis. *Medical Image Analysis*, 42, 60-88. [https://www.sciencedirect.com/science/article/abs/pii/S1361841517301135](https://www.sciencedirect.com/science/article/abs/pii/S1361841517301135)

**\[16\]** Slomka, P. J., Dey, D., Sitek, A., Motwani, M., Berman, D. S., & Germano, G. (2017). Artificial intelligence in cardiovascular imaging. *JACC: Cardiovascular Imaging*, 10(6), 615-626. [https://pmc.ncbi.nlm.nih.gov/articles/PMC7350824/](https://pmc.ncbi.nlm.nih.gov/articles/PMC7350824/)

**\[17\]** Antiga, L., Piccinelli, M., Botti, L., Ene-Iordache, B., Remuzzi, A., & Steinman, D. A. (2008). An image-based modeling framework for patient-specific computational hemodynamics. *Medical & Biological Engineering & Computing*, 46(11), 1097-1112. [https://link.springer.com/article/10.1007/s11517-008-0420-1](https://link.springer.com/article/10.1007/s11517-008-0420-1)

**\[18\]** Zhang, X., Zhang, B., & Zhang, F. (2024). Stenosis detection and quantification of coronary artery using machine learning and deep learning. *Angiology*, 75(5), 405-416. [https://journals.sagepub.com/doi/abs/10.1177/00033197231187063](https://journals.sagepub.com/doi/abs/10.1177/00033197231187063)

**\[19\]** Hong, Y., Commandeur, F., Cadet, S., Goeller, M., Doris, M. K., Chen, X., ... & Dey, D. (2019). Deep learning-based stenosis quantification from coronary CT angiography. In *Proceedings of SPIE* (Vol. 10949, p. 109492I). [https://pmc.ncbi.nlm.nih.gov/articles/PMC6874408/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6874408/)

**\[20\]** Borkin, M., Gajos, K., Peters, A., Mitsouras, D., Melchionna, S., Rybicki, F., ... & Pfister, H. (2011). Evaluation of artery visualizations for heart disease diagnosis. *IEEE Transactions on Visualization and Computer Graphics*, 17(12), 2479-2488. [https://ieeexplore.ieee.org/abstract/document/6065015](https://ieeexplore.ieee.org/abstract/document/6065015)

**\[21\]** Clapers Colet, M. (2025). *Automatic Labeling of Coronary Artery Segments: Multi-Strategy Development and Evaluation* \[Bachelor's thesis, Universitat Pompeu Fabra\]. 

**\[22\]** Burrull, E. (2023). *Stenosis Quantification Pipeline* \[Internal Research, Hospital de la Santa Creu i Sant Pau\]. 

**\[23\]** Kelly, C. J., Karthikesalingam, A., Suleyman, M., Corrado, G., & King, D. (2019). Key challenges for delivering clinical impact with artificial intelligence. *BMC Medicine*, 17(1), 1-9. [https://link.springer.com/article/10.1186/s12916-019-1426-2](https://link.springer.com/article/10.1186/s12916-019-1426-2)

**\[24\]** Isensee, F., Jaeger, P. F., Kohl, S. A., Petersen, J., & Maier-Hein, K. H. (2021). nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. *Nature Methods*, 18(2), 203-211. [https://www.nature.com/articles/s41592-020-01008-z](https://www.nature.com/articles/s41592-020-01008-z)

**\[25\]** Cleerly, Inc. (2024). *Cleerly \- AI-driven heart disease care*. Retrieved from [https://cleerlyhealth.com/](https://cleerlyhealth.com/)  

**\[26\]** Çiçek, Ö., Abdulkadir, A., Lienkamp, S. S., Brox, T., & Ronneberger, O. (2016). 3D U-Net: learning dense volumetric segmentation from sparse annotation. In *Medical Image Computing and Computer-Assisted Intervention (MICCAI)* (pp. 424-432). [https://link.springer.com/chapter/10.1007/978-3-319-46723-8\_49](https://link.springer.com/chapter/10.1007/978-3-319-46723-8_49)

**\[27\]** Yang, H., et al. (2020). CPR-GCN: Conditional partial-residual graph convolutional network in automated anatomical labeling of coronary arteries. In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)* (pp. 3802-3810). [https://openaccess.thecvf.com/content\_CVPR\_2020/html/Yang\_CPR-GCN\_Conditional\_Partial-Residual\_Graph\_Convolutional\_Network\_in\_Automated\_Anatomical\_Labeling\_CVPR\_2020\_paper.html](https://openaccess.thecvf.com/content_CVPR_2020/html/Yang_CPR-GCN_Conditional_Partial-Residual_Graph_Convolutional_Network_in_Automated_Anatomical_Labeling_CVPR_2020_paper.html)

**\[28\]** Sanchez Gomez, C. (2022). *Coronary artery segmentation using Transformer Neural Networks* \[Master's thesis, Universitat de Barcelona\].  [https://diposit.ub.edu/items/01c3ed6a-3bff-4ba9-879d-6b5750536d0e](https://diposit.ub.edu/items/01c3ed6a-3bff-4ba9-879d-6b5750536d0e)

**\[29\]** Artrya Ltd. (2024). *Artrya Salix Coronary Anatomy (SCA) \- AI-driven detection of vulnerable plaque*. Retrieved from [https://www.artrya.com/](https://www.artrya.com/) 

