### **Artery Geometry Extraction: Hybrid Approach** 

#### **Phase 1: Pre-processing & RCA/LCA Separation**

1. **Load the unified mask:** Read the .nrrd file and extract the raw 3D NumPy array.  
2. **Connected Components:** Use scipy.ndimage.label to identify the distinct, unconnected objects in the 3D grid. The two largest objects will be the RCA and LCA.  
3. **Center of Mass Sorting:** Implement Maren's logic to calculate the spatial center of each object. The one furthest to the right (lower X coordinate in standard medical spacing) is the RCA; the one furthest to the left is the LCA.  
4. **Split the Data:** Create two separate binary arrays (one for RCA, one for LCA).  
   

#### **Phase 2: The Loop (Process RCA, then process LCA)**

From here, we put the following steps inside a loop so the exact same logic runs for both the RCA and the LCA individually.

**Step 2A: Mesh Generation & Smoothing**

* Convert the separated numpy array back into a VMTK vtkImageData object.  
* Run vmtkMarchingCubes to create the surface.  
* Run vmtkSurfaceSmoothing (with our optimized **20 iterations**) to get the continuous mathematical mesh.


**Step 2B: Automated Seed Point Extraction (Maren's "Scout")**

* Run skimage.morphology.skeletonize\_3d on the separated binary array.  
* Scan the resulting skeleton for **endpoints** (voxels with exactly 1 neighbor).  
* Compute the Distance Transform of the binary mask to find the thickness at each endpoint.  
* Assign the endpoint with the largest thickness as the Source (Ostium). Assign all other endpoints as Targets (Distal branches).  
* Convert these voxel indices (z, y, x) into physical coordinates (X, Y, Z) in millimeters using the Origin and Spacing metadata.  
* Snap these coordinates to the nearest vertex on the smoothed mesh.


**Step 2C: VMTK Mathematical Centerline Extraction**

* Feed the smoothed mesh, the Source coordinate, and the Target coordinates into vmtkscripts.vmtkCenterlines.  
* Execute the algorithm to trace the mathematically optimal geometric centerlines.


#### **Phase 3: Data Extraction & DataFrame Construction**

1. Extract the raw arrays from the VMTK centerline output. Specifically, pull the Points array (Px, Py, Pz) and the MaximumInscribedSphereRadius array.  
2. Create a temporary Pandas DataFrame for the current artery containing:  
   * Sample\_ID: The identifier you passed at the start (e.g., "Normal\_1").  
   * Artery\_Type: The current loop variable ("RCA" or "LCA").  
   * Px, Py, Pz: The physical coordinates of the centerline.  
   * Radius: The inscribed radius at that exact point.  
3. Append this temporary DataFrame to a "Master" DataFrame.

### **Why does this architecture work?**

By combining Maren's separation and skeletonization logic with VMTK's exact geometry extraction, the entire pipeline becomes 100% automated. You could point this script at a folder of 100 ASOCA patients, hit "Run", go grab a coffee, and come back to a massive, perfectly formatted CSV file ready for stenosis quantification.  
