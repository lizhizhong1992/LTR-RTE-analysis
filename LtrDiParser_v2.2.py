from collections import defaultdict
from Bio import SeqIO
import re

from Bio.SeqRecord import SeqRecord

from RT_gyDB_hmm import classification

import sys

STATUS_TE_FULL = "complete"

class LTR():
    def __init__(self,ID, chromosome, start, end, strand):
        self.ID = ID
        self.start = start
        self.end = end
        self.chromosome = chromosome
        self.strand = strand
        self.domains_required = ['GAG', "AP", 'RT', 'RNaseH', 'INT']
        self.domains_skipped = ["LTR_retrotransposon","long_terminal_repeat","target_site_duplication"] # they will present anyway from LTRharvest
        self.outGff3 = ''
        self.features = {"LTRharvest":defaultdict(list), "LTRdigest":defaultdict(list)}
        self.domains_present_in_TE = {} # {domain:[host1, host2,...]}
        self.class_d = self._getClassificationDi()         #param dictionary: dictionary from D:\PycharmProjects\MossRepeatomArticle\Scripts\RT_classification_gyDB_hmm.tab
        self.classification_status_domains  = [] #[[domains], [classification (or "-")], [status ("truncated", "complete", "false-positive")]] returned by  classify


    def _getClassificationDi(self):
        class_d = {}
        class_d['micropia'] = "Ty3/Gypsy"
        class_d['v'] = "Ty3/Gypsy"
        class_d['412'] = "Ty3/Gypsy"
        class_d['17'] = "Ty3/Gypsy"
        class_d['a'] = "Ty3/Gypsy"
        class_d['b'] = "Ty3/Gypsy"
        class_d['codi'] = "Ty1/Copia"
        class_d["galea"] = "Ty1/Copia"

        class_d.update(classification)
        return class_d

    def addFeature(self, source, name, chromosome, start, end, evalue):
        self.features[source][name].append([chromosome, start, end, evalue])

    def getBasicInfo(self):
        return [self.ID, self.start, self.end]

    def getLTRs(self):
        return self.features["LTRharvest"]['long_terminal_repeat']

    def getAllFeatures(self):
        toret = []
        for source in self.features:
            for features in self.features[source]:
                toret.append(features)
        return toret

    def getLTRdigestDomainsCoordinates(self):
        byDomain = []
        for source in self.features:
            for features in self.features[source]:
                for coordinates in self.features[source][features]:
                    domain = features
                    if source != "LTRharvest":
                        domain = features.split("_")[0]

                    coordinates.append(domain)

                    byDomain.append(coordinates)

        return byDomain


    def isFull(self):
        if not self.classification_status_domains:
            self.classify()

        return self.classification_status_domains[-1] == STATUS_TE_FULL # != "false-positive" #== STATUS_TE_FULL

    def classify(self):
        if self.classification_status_domains:
            return self.classification_status_domains

        self.domains_present_in_TE = self.splitBydomain()

        """
        :return: [[domains], [classification (or "-")], [status ("truncated", "complete", "false-positive")]]
        """
        domains_required = self.domains_required
        domains_skipped = self.domains_skipped #["LTR_retrotransposon","long_terminal_repeat","target_site_duplication"] # they will present anyway from LTRharvest
        domains = []
        classification = []
        status = ""

        all_clas = []
        for dom in self.domains_present_in_TE:
            if dom == "RT":
                for rt_source in self.domains_present_in_TE["RT"]:

                    if rt_source in self.class_d:
                        all_clas.append(self.class_d[rt_source])
                    else:
                        all_clas.append("Unknown:{}".format(rt_source))
            if dom not in domains_skipped:
                domains.append(dom)

        absence_domains = ",".join([i for i in domains_required if i not in self.domains_present_in_TE])
        domains_present_short = [i for i in domains_required if i in self.domains_present_in_TE]

        if len(domains_present_short) == 5:
            status = STATUS_TE_FULL
        elif len(domains_present_short) == 0:
            status = "false-positive"
        else:
            status = "truncated TE:{} not found".format(absence_domains)

        domains = sorted(domains)

        if not all_clas:
            classification = "-"
        else:
            classification = str(max({i:all_clas.count(i) for i in set(all_clas)}, key=lambda x:x[0]))

        domains = ",".join([i for i in domains])

        self.classification_status_domains = [domains, classification, status]
        return [domains, classification, status]

    def getBestHit(self, domain):
        sizes = []
        if domain in self.classification_status_domains[0]:
            #print(self.features["LTRdigest"])
            for features in self.features["LTRdigest"]:
                    if len(self.features["LTRdigest"][features]) > 4:
                        domain_name = features
                        owner_domain = features
                        if "_" in features:
                            domain_name = features.split("_")[0]
                            owner_domain = features.split("_")[1]

                        if domain_name == domain:
                            #print(self.features["LTRdigest"][features])
                            sizes.append([owner_domain,abs(float(self.features["LTRdigest"][features][0][3])), abs(int(self.features["LTRdigest"][features][0][2])) - int(self.features["LTRdigest"][features][0][1])])

            if len(sizes) > 1:
                sizes = [i for i in sizes if i[0] not in ["caulimovirus", "badnavirus", "cavemovirus", "soymovirus"]]
            if len(sizes) != 0:
                min_evalue = min(sizes, key=lambda x: x[1])[1]
                Len = 0
                current_best = ""
                all_best_evalue = []

                for i in sizes:
                    if i[1] == min_evalue:
                        all_best_evalue.append(i[0])
                        if i[2] > Len:
                            Len = i[2]
                            current_best = i[0]

                    return current_best
            else:
                return "nd"
        else:
            return "nd"


    def splitBydomain(self):
        byDomain = defaultdict(list)
        for source in self.features:
            for features in self.features[source]:
                if source == "LTRharvest":
                    byDomain[features].append(features)
                elif "_" in features:
                    byDomain[features.split("_")[0]].append(features.split("_")[1])
                else:
                    byDomain[features].append(features)
        return byDomain

    def getDomainsPresenceNot(self):
        doms_pres_not = []

        for i in self.domains_required:
            if i in self.domains_present_in_TE:
                doms_pres_not.append(i)
            else:
                doms_pres_not.append("-")

        return "\t".join(doms_pres_not)


class LtrDiParser():

    def __init__(self, gff3File, mask_for_chromosome_id = ".[]0", sequence_name = None):
        self.sequence_name = sequence_name
        self.gff3File = self.modifyGff3(gff3File)
        self.LTRs = defaultdict(LTR)
        self.mask_for_chromosome_id = mask_for_chromosome_id ##where split and which index to extract chromosome id from sequence id
        self.TE_classification_tab = {} #te_id:[chromosome, start, end, length, classification]
        self.run()

    def run(self):
        self.__readGff()

    def __getChromosomeId(self, seqId):
        return seqId.split(self.mask_for_chromosome_id.split('[]')[0])[int(self.mask_for_chromosome_id.split('[]')[1])]

    def __readGff(self):
        with open(self.gff3File) as gff_file:
            start_new_LTR = False
            for num,lines in enumerate(gff_file):
                sp = lines.rstrip().split("\t")
                if not lines.startswith("##gff-version"):
                    if lines.startswith("###") or num == 1:
                        start_new_LTR = True
                    elif start_new_LTR:
                        start_new_LTR = False
                        newLTR = LTR(sp[-1].split("=")[1], sp[0].split(' ')[0], sp[3], sp[4], sp[6])
                        self.LTRs[newLTR.ID] = newLTR
                    else:
                        if sp[1] == "LTRharvest" or ";name=" not in sp[-1]:
                            featureName = sp[2]
                        else:
                            featureName = sp[-1].split(";name=")[1]
                        self.LTRs[newLTR.ID].addFeature(sp[1],featureName, sp[0], sp[3], sp[4], sp[5])

        print("Number of LTRs found: ", len(self.LTRs))


    def getAllfeatureNames(self):
        fn = []
        domain = []
        domain_presents = []
        for ltrs in self.LTRs:
            fn += self.LTRs[ltrs].getAllFeatures()
            dLTRs = self.LTRs[ltrs].splitBydomain()
            domain += dLTRs
            domain_presents.append(",".join(sorted(dLTRs)))

    def getAllFull(self):
        cnt = 0
        for ltrs in self.LTRs:
            if self.LTRs[ltrs].isFull():
                cnt += 1

    def getFastaFullLtrs(self, genomeFasta):
        cnt_t = 0
        per_chromosome = defaultdict(list)
        for ltrs in self.LTRs:
            if self.LTRs[ltrs].isFull():
                per_chromosome[self.LTRs[ltrs].chromosome].append(self.LTRs[ltrs].getBasicInfo())
                cnt_t += 1

        cnt = 0

        with open("Full_LTRs_transposons_{}".format(genomeFasta.split("/")[-1]), "w") as outFile:
            for seq in SeqIO.parse(genomeFasta, "fasta"):
                if seq.id in per_chromosome:
                    chromosome_seq = str(seq.seq)
                    for ltrs in per_chromosome[seq.id]:
                        #print(ltrs)
                        start, end = min([int(ltrs[1]), int(ltrs[2])]), max(([int(ltrs[1]), int(ltrs[2])]))
                        outFile.write(">" + ltrs[0] + " {2}:{0}_{1}".format(start-1,end, seq.id) + "\n" +  chromosome_seq[start-1:end] + "\n")
                        cnt += 1

        print("{0} of {1} sequences in the file".format(cnt, cnt_t))


    def getClassification(self):
        outfile_name = "{}.fullLTRclassification".format(self.gff3File)
        with open(outfile_name, "w") as outfile:
            outfile.write("\t".join(["TE_id", "Chromosome", "Start", "End", "Estimation", "Classification", "Domains found", "hit_RT", 'GAG', "AP", 'RT', 'RNaseH', 'INT']) + "\n")


            cnt_fulll = 0

            for ltrs in self.LTRs:
                domains, classification, status = self.LTRs[ltrs].classify()  # return [domains, classification (or "-"), status ("truncated", "complete", "false-positive")]
                base = "\t".join([ltrs+"<*>"+self.LTRs[ltrs].chromosome,
                                  self.LTRs[ltrs].chromosome,
                                  self.LTRs[ltrs].start, self.LTRs[ltrs].end,
                                  status, classification, domains, "-", self.LTRs[ltrs].getDomainsPresenceNot()
                                 ])
                #te_id: [chromosome, start, end, length, classification]
                self.TE_classification_tab[self.LTRs[ltrs].chromosome] = [self.LTRs[ltrs].chromosome,self.LTRs[ltrs].start, self.LTRs[ltrs].end,
                                                                          abs(int(self.LTRs[ltrs].start) - int(self.LTRs[ltrs].end))]
                outfile.write(base + "\n")

                if self.LTRs[ltrs].isFull():
                    cnt_fulll += 1

            print("Number of full-length TEs:", cnt_fulll)

        return outfile_name

    def getBEDfileDomains(self, from0 = True):
        with open("{}.bed".format(self.gff3File[:-4]), "w") as outfile:
            for re in self.LTRs:
                per_domain = defaultdict(list)
                #if self.LTRs[re].isFull():
                al_domains_matrix = self.LTRs[re].getLTRdigestDomainsCoordinates()

                for al_domains in al_domains_matrix:
                    per_domain[al_domains[-1]].append(al_domains)

                start = int(per_domain["LTR_retrotransposon"][0][1])
                for domains_unqiue in per_domain:
                    te_id = self.LTRs[re].chromosome.replace("_","|") + "_" + self.LTRs[re].start + "_" + self.LTRs[re].end
                    if domains_unqiue != "long_terminal_repeat":
                        longest_hit = max(per_domain[domains_unqiue], key=lambda x:abs(int(x[1]) - int(x[2])))
                        longest_hit[0] = longest_hit[0].replace("_", "|")
                        longest_hit[0] = longest_hit[0].split(" ")[0]
                        longest_hit.pop(3)
                        #print(longest_hit) #['tig00145920', '199601', '199604', 'target_site_duplication']

                        if from0:
                            longest_hit[1] = str(int(longest_hit[1]) - start)
                            longest_hit[2] = str(int(longest_hit[2]) - start)
                        outfile.write("\t".join(longest_hit) + "\n") #+ "\t"  + te_id + "\n")
                    else:
                        for ltrs in per_domain[domains_unqiue]:
                            ltrs[0] = ltrs[0].replace("_","|")
                            ltrs[0] = ltrs[0].split(" ")[0]
                            ltrs.pop(3)
                            #print(ltrs)
                            if from0:
                                ltrs[1] = str(int(ltrs[1]) - start)
                                ltrs[2] = str(int(ltrs[2]) - start)
                            outfile.write("\t".join(ltrs) + "\n") # + "\t" + te_id + "\n")


    def gff3Tobed(self):
        with open("{}.bed".format(self.gff3File[:-4]), "w") as outfile:
            for re in self.LTRs:
                per_domain = defaultdict(list)
                al_domains_matrix = self.LTRs[re].getLTRdigestDomainsCoordinates()

                for al_domains in al_domains_matrix:
                    per_domain[al_domains[-1]].append(al_domains)

                start = int(per_domain["LTR_retrotransposon"][0][1])
                for domains_unqiue in per_domain:
                    if domains_unqiue != "long_terminal_repeat":
                        longest_hit = max(per_domain[domains_unqiue], key=lambda x:abs(int(x[1]) - int(x[2])))
                        outfile.write("\t".join(longest_hit) + "\t" + re + "\n")
                    else:
                        for ltrs in per_domain[domains_unqiue]:
                            outfile.write("\t".join(ltrs) + "\t" + re + "\n")

    def get_LTRs_fasta(self, genome, onlyFull = False):
        """
        :return: two LTR fasta files for current genome and LTR sequence
        """
        ltr_3_file = genome + ".idx_3ltr.fas"
        ltr_5_file = genome + ".idx_5ltr.fas"
        TE_body = genome + ".TE_body.fasta"

        files_ltr_out = [ltr_5_file, ltr_3_file]
        cnt = 0
        ltr_dic = defaultdict(list) #'chromosome': [LTR objects]
        for TEs in self.LTRs:
            if onlyFull:
                if self.LTRs[TEs].isFull():
                    ltr_dic[self.LTRs[TEs].chromosome].append(self.LTRs[TEs])
            else:
                ltr_dic[self.LTRs[TEs].chromosome].append(self.LTRs[TEs])
        with open(ltr_3_file, 'w') as ltr3, open(ltr_5_file, 'w') as ltr5, open(TE_body, 'w') as out_fasta:
            for seq in SeqIO.parse(genome, 'fasta'):
                if seq.id in ltr_dic:
                    for LTRs in ltr_dic[seq.id]: # iterate through LTRs for this chromosome
                        coords = LTRs.getLTRs() #[[chr, start, end],[chr, start, end]] for 5 and 3 LTRs
                        #print(coords)
                        ltr_id = "{0}_{1}_{2}".format(seq.id, LTRs.start, LTRs.end)

                        # 3' lTR
                        ltr_3_seq = seq.seq[int(coords[1][1]): int(coords[1][2])]
                        sr = SeqRecord(ltr_3_seq,id=ltr_id,description="3'-LTR")
                        SeqIO.write(sr, ltr3, "fasta")
                        cnt += 1

                        # 5' lTR
                        ltr_5_seq = seq.seq[int(coords[0][1]): int(coords[0][2])]
                        sr = SeqRecord(ltr_5_seq, id=ltr_id, description="5'-LTR")
                        SeqIO.write(sr, ltr5, "fasta")

                        #TE body
                        te_body= seq.seq[int(LTRs.start): int(LTRs.end)]
                        sr = SeqRecord(te_body, id=ltr_id, description="TE_predicted")
                        SeqIO.write(sr, out_fasta, 'fasta')

        print("Number of LTRs sequences predicted by LTRharvest in fasta file", cnt)




    def modifyGff3(self, LTRharvest_output):
            """
            instead of real chromosome name LTharvest put Seq.. names. This function change chromosome and scaffolds names
            :param LTRharvest_output:
            :return:
            """
            l1_new_names = [] # seq...
            l2_real_names = [] # Chr...
            d = {} # number in gff3 annotation : real chromosome name
            real_name_patter = re.compile("^#[^#]")
            outfile_id = LTRharvest_output + '_modified'
            real_names_start = False
            with open(LTRharvest_output) as infile, open(outfile_id, "w") as outfile:
                for num, lines in enumerate(infile):
                    if num != 0:
                        ## pseudo names
                        if lines.startswith("##s"):
                            l1_new_names.append(lines.split(" ")[3].split("seq")[-1])
                        #real names
                        elif real_name_patter.search(lines):
                            l2_real_names.append(lines.rstrip()[1:])
                        #blank line
                        elif lines.startswith("###"):
                            outfile.write(lines)
                        #coordinates
                        else:
                            if not l2_real_names: #when only one sequence was in gff3 then no real names will be in gff3 file header
                                l2_real_names.append(self.sequence_name)

                            if not real_names_start:
                                l1_new_names = [int(i) for i in l1_new_names]
                                for i,nam in enumerate(sorted(l1_new_names)):
                                    d["seq" + str(nam)] =  l2_real_names[i]
                                real_names_start = True
                            sp = lines.split("\t")
                            sp[0] = d[sp[0]]
                            new_line = "\t".join(sp)
                            outfile.write(new_line)
                    else:
                        outfile.write("###\n")
            return outfile_id

    def changeIDseqs(self, fastafile):
        with open("modifiedIDs_" + fastafile, "w") as outfile:
            for seq in SeqIO.parse(fastafile, "fasta"):
                seq.id = seq.id + "_" + "_".join(seq.description.split(" "))

                SeqIO.write(seq, outfile, "fasta")

    def findOverlap(self, chromosome, start, end):
        for ltrs in self.LTRs:
            ltrs = self.LTRs[ltrs]
            ltrs.start, ltrs.end = int(ltrs.start), int(ltrs.end)
            if ltrs.chromosome == chromosome:
                if not(start > ltrs.end and end > ltrs.end) and not (start < ltrs.start and end < ltrs.start):
                    print(ltrs.ID)

    def getBED_LTR_coordinates(self, fullOnly = False):
        outFile = self.gff3File + ".bed"
        if fullOnly:
            outFile = self.gff3File + "fullOnly.bed"
        with open(outFile, "w") as outFile:
            cnt = 0
            ind = True
            for LTR_id in self.LTRs:
                #for sunflower
                if fullOnly:
                    ind = self.LTRs[LTR_id].isFull()
                if ind:
                    self.LTRs[LTR_id].chromosome = self.LTRs[LTR_id].chromosome.replace("_","|")
                    outFile.write("\t".join([self.LTRs[LTR_id].chromosome,self.LTRs[LTR_id].start, self.LTRs[LTR_id].end]) + "\n")
                    cnt += 1
        print("TEs collected:", cnt)

    def getGTF_for_StringTie2(self):
        with open(self.gff3File + ".gtf", "w") as outFile:
            cnt = 0
            for LTR_id in self.LTRs:
                TE = self.LTRs[LTR_id]
                TE.chromosome = TE.chromosome.replace("_","|")

                line = "{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}\t{8}\n".format(
                    TE.chromosome,
                    "StringTie",
                    "transcript",
                    TE.start,
                    TE.end,
                    100,
                    ".",
                    ".",
                    'gene_id "{0}_{1}_{2}"; transcript_id "{0}_{1}_{2}"'.format(TE.chromosome, TE.start, TE.end)
                )
                outFile.write(line)

LD = LtrDiParser(sys.argv[1])
genome_fasta = sys.argv[2]
LD.getFastaFullLtrs(genome_fasta)
LD.get_LTRs_fasta(genome_fasta, onlyFull = True)


