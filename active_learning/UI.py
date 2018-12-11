#
# UI.py
#
# Main entry point for the GUI-based view of the active learning project.
#

#%% Constants and imports

import sys
from PyQt5.QtWidgets import QTabWidget, QMainWindow, QApplication, QSizePolicy, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QListView, QProgressBar, QInputDialog
from UIComponents.GridWidget import GridWidget
from DL.sqlite_data_loader import SQLDataLoader
from DL.Engine import Engine

from sklearn.cluster import DBSCAN
from sklearn.metrics import pairwise_distances_argmin_min

from UIComponents.DBObjects import *
from DL.utils import *
from DL.networks import *

# from multiprocessing import Process

#%% Core UI

class UI(QTabWidget):

    def __init__(self):
        super(UI, self).__init__()
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Fixed)
        policy.setVerticalPolicy(QSizePolicy.Fixed)
        #policy.setHeightForWidth(True)

        self.initUI()
        self.currentChanged.connect(self.onChange)

    def onChange(event):
        if event.currentIndex() in (0,1,2):
          event.currentWidget().showCurrentPage()
       
    def initUI(self):
        global species
        species = QStringListModel()
        speciesList=[]
        all_species= Category.select()
        for x in all_species:
          speciesList.append(x.name)
        speciesList.append("Add New")
        species.setStringList(speciesList)

        prefered_image_width=(0.485*app.primaryScreen().size().width())/4
        self.tab1 = GridWidget(DetectionKind.ActiveDetection, prefered_image_width, num_cols=3, labeler=True)
        self.tab2 = GridWidget(DetectionKind.UserDetection, prefered_image_width)
        self.tab3 = GridWidget(DetectionKind.ModelDetection, prefered_image_width)
        self.tab4 = QWidget()
        self.setWindowTitle( 'Labeler' )
        self.addTab(self.tab1,"Unlabeled")# ("+str(len(self.unlabeled))+")")
        self.addTab(self.tab2,"User Labeled")# ("+str(len(self.labeled))+")")
        self.addTab(self.tab3,"Model Labeled")# ("+str(species.rowCount()-1)+")")
        self.addTab(self.tab4,"Species")# ("+str(species.rowCount()-1)+")")
        #print(self.tab1.parentWidget(),self)
        self.tab1.confirm = QPushButton('Confirm Images')
        self.tab1.start = QPushButton('Start Learning')
        self.tab1.horizontalLayout.addWidget(self.tab1.confirm)
        self.tab1.horizontalLayout.addWidget(self.tab1.start)

        self.tab4.verticalLayout= QVBoxLayout(self.tab4)
        self.tab4.speciesList= QListView()
        self.tab4.speciesList.setModel(species)
        self.tab4.speciesList.setRowHidden(len(species.stringList())-1, True)
        self.tab4.add = QPushButton('Add' )
        self.tab4.update= QPushButton('Update')
        self.tab4.horizontalLayout= QHBoxLayout()
        self.tab4.horizontalLayout.addWidget(self.tab4.add) 
        self.tab4.horizontalLayout.addWidget(self.tab4.update) 
        self.tab4.verticalLayout.addWidget(self.tab4.speciesList)
        self.tab4.verticalLayout.addLayout(self.tab4.horizontalLayout)
        self.setWindowTitle( 'Labeler' )
        self.tab1.confirm.clicked.connect(self.confirm)
        self.tab1.start.clicked.connect(self.active)
        self.tab4.add.clicked.connect(self.addSpecies)
        self.tab4.update.clicked.connect(self.updateSpecies)

    def addSpecies(self, event):
      text, ok = QInputDialog.getText(self, 'Enter Name', 'Enter the name of species:')
      rows= self.tab4.speciesList.model().rowCount()
      self.tab4.speciesList.model().insertRows(rows-1, 1);
      self.tab4.speciesList.model().setData(self.tab4.speciesList.model().index(rows-1), text, Qt.EditRole)
      self.syncSpecies()

    def syncSpecies(self):
      global species
      for s in species.stringList():
        x= Category.select().where(Category.name==s)
        if not x.exists() and s!='Add New':
          cat=Category()
          cat.name=s
          cat.save()   

    def updateSpecies(self,event):
      index= self.tab4.speciesList.currentIndex()
      text, ok = QInputDialog.getText(self, 'Enter Name', 'Enter the name of species:', text= self.tab4.speciesList.model().data(index, Qt.DisplayRole))
      self.tab4.speciesList.model().setData(index, text, Qt.EditRole)
      self.syncSpecies()

    def confirm(self,event):
      for i in range(self.tab1.num_rows):
        for j in range(self.tab1.num_cols):
          index= i*self.tab1.num_cols+j
          final= self.tab1.images[index].getFinal()
          for label in final[1]:
            det= Detection.get(Detection.id==label[1][0])
            det.category= label[0]
            det.kind= DetectionKind.UserDetection.value
            det.save()
      self.tab1.page=1
      self.tab1.showCurrentPage()

    def active(self,event):
        self.parentWidget().statusBar().showMessage("Start Learning")
        checkpoint= load_checkpoint('../merge/triplet_model_0054.tar')
        run_dataset = SQLDataLoader(DetectionKind.ModelDetection, "/home/pangolin/all_crops/SS_full_crops", False, num_workers= 8, batch_size= 2048)
        #run_dataset.setup(Detection.select(Detection.id,Category.id).join(Category).where(Detection.kind==DetectionKind.ModelDetection.value).limit(250000))
        num_classes= len(run_dataset.getClassesInfo())
        print("Num Classes= "+str(num_classes))
        run_loader = run_dataset.getSingleLoader()
        embedding_net = EmbeddingNet(checkpoint['arch'], checkpoint['feat_dim'])
        if checkpoint['loss_type'].lower()=='center':
            model = torch.nn.DataParallel(ClassificationNet(embedding_net, n_classes=14)).cuda()
        else:
            model= torch.nn.DataParallel(embedding_net).cuda()
        model.load_state_dict(checkpoint['state_dict'])
        self.parentWidget().progressBar.setMaximum(len(run_dataset)//2048)
        e=Engine(model,None,None, verbose=True,progressBar= self.parentWidget().progressBar)
        self.parentWidget().statusBar().showMessage("Extract Embeddings")
        embd, label, paths = e.predict(run_loader, load_info=True)
        self.parentWidget().statusBar().showMessage("Clustring Images")
        self.parentWidget().progressBar.setMaximum(0)
        new_selected= self.selectSamples(embd,paths,300)
        self.tab1.update()
        self.tab1.showCurrentPage(force=True)
        self.parentWidget().statusBar().showMessage("Clustring Finished")

    def selectSamples(self, embd, paths, n):
        selected_set= set()
        while len(selected_set)<n:
            print(len(selected_set))
            rand_ind= np.random.choice(np.arange(embd.shape[0]),1000, replace=False)
            db = DBSCAN(eps=1, min_samples=5,n_jobs=-1).fit(embd[rand_ind])
            indices=set()
            for i,x in enumerate(db.labels_):
              if x==-1 and self.getDistance(embd,indices,rand_ind[i])>0.7 and self.getDistance(embd,selected_set,rand_ind[i])>0.7:
                indices.add(rand_ind[i])
            self.moveRecords(DetectionKind.ModelDetection, DetectionKind.ActiveDetection, [paths[i] for i in indices.difference(selected_set)])
            selected_set= selected_set.union(indices)
            #print(indices,selected_set)
        return selected_set

    def getDistance(self,embd,archive,sample):
      if len(archive)==0:
          return 100
      else:
          return pairwise_distances_argmin_min(embd[sample].reshape(1, -1),embd[np.asarray(list(archive),dtype=np.int32)])[1]

    def moveRecords(self,srcKind,destKind,rList):
      query= Detection.update(kind=destKind.value).where(Detection.id.in_(rList), Detection.kind==srcKind.value)
      #print(query.sql())
      query.execute()
      #src.delete().where(src.image_id<<rList))

            #det= UserDetection.create(category_id=0, id=str(index+label[1][2]),image_id=final[0], bbox_X=label[1][0], bbox_Y=label[1][1], bbox_W=label[1][2], bbox_H=label[1][3])
      #for x in self.tab1.grid.tags:
      #  x.delete_instance()


class App(QMainWindow):
 
    def __init__(self):
        super().__init__()
        self.title = 'Active Labeler'
        screen = app.primaryScreen()
        size = screen.size()
        self.setWindowTitle(self.title)
        self.setGeometry(0, 0, size.width()/2, size.height()-80)
        db = SqliteDatabase('SS.db')
        proxy.initialize(db)
        db.connect()

        #db.create_tables([Detection])
        self.table_widget = UI()
        self.setCentralWidget(self.table_widget)
        self.statusBar().showMessage('Ready')
        self.progressBar = QProgressBar()
        self.statusBar().addPermanentWidget(self.progressBar)
        # This is simply to show the bar
        self.progressBar.setGeometry(30, 40, 200, 25)
        self.show()


#%% Driver
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.centralWidget().tab1.showCurrentPage()
    #p = Process(target=ex.active, args=())
    #p.start()
    #p.join()

    #ex.active()
    #ex.centralWidget().setCurrentIndex(1)
    sys.exit(app.exec_())
    #main()
